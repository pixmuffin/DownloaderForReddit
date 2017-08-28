"""
Downloader for Reddit takes a list of reddit users and subreddits and downloads content posted to reddit either by the
users or on the subreddits.


Copyright (C) 2017, Kyle Hickey


This file is part of the Downloader for Reddit.

Downloader for Reddit is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Downloader for Reddit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Downloader for Reddit.  If not, see <http://www.gnu.org/licenses/>.
"""


import datetime
import os
import re
import subprocess
import sys
import time

from PyQt5 import QtWidgets, QtCore, QtGui

import Core.Injector
from Core.Messages import Message
from GUI_Resources.UserSettingsDialog_auto import Ui_user_settings_dialog


class UserSettingsDialog(QtWidgets.QDialog, Ui_user_settings_dialog):

    single_download = QtCore.pyqtSignal(object)

    def __init__(self, list_model, clicked_user):
        """
        Class that forms the user dialog box that is accessed by right-clicking a user in the GUI window to adjust
        settings for individual users. Also contains a list model of all other users in the same list so other users can
        be selected without having to exit the dialog.

        This class is also used to display recently downloaded users content.  When used in this capacity some of the
        features are overridden or changed at the time that the instance of this class is created

        :param list_model: The underlying list model that is currently displayed in the GUI
        :param clicked_user: The user name that is right-clicked to bring the menu up.
        """
        QtWidgets.QDialog.__init__(self)
        self.setupUi(self)
        try:
            self.user_list = list_model.reddit_object_list
        except AttributeError:
            self.user_list = list_model
        self.display_list = [x.name for x in self.user_list]
        self.current_user = clicked_user
        self.restore_defaults = False
        self.closed = False

        self.settings_manager = Core.Injector.get_settings_manager()
        self.restoreGeometry(self.settings_manager.user_settings_dialog_geom)
        self.user_content_icons_full_width = self.settings_manager.user_content_icons_full_width
        self.user_content_icon_size = self.settings_manager.user_content_icon_size
        self.current_item_display_list = self.settings_manager.current_user_settings_item_display_list

        self.show_downloads = True

        self.item_display_reddit_object_link_dict = {'previous_downloads': self.current_user.already_downloaded,
                                                     'saved_content': self.current_user.saved_content,
                                                     'saved_submissions': self.current_user.saved_submissions}

        self.download_user_button.clicked.connect(self.download_single)
        self.view_downloads_button.clicked.connect(self.change_page)

        self.cust_save_path_dialog.clicked.connect(self.select_save_path_dialog)

        for user in self.display_list:
            self.user_list_widget.addItem(user)
        self.user_list_widget.setCurrentRow(self.display_list.index(self.current_user.name))
        self.user_list_widget.currentRowChanged.connect(self.list_item_change)

        self.save_cancel_buton_box.accepted.connect(self.accept)
        self.save_cancel_buton_box.rejected.connect(self.close)
        self.restore_defaults_button.clicked.connect(self.set_restore_defaults)

        self.name_downloads_combo.addItems(('Image/Album Id', 'Post Title'))

        self.saved_content_name_dict = {}
        self.setup()

        self.page_one_geom = None
        self.page_two_geom = None

        self.user_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.user_list_widget.customContextMenuRequested.connect(self.user_list_widget_right_click)
        self.user_list_widget.doubleClicked.connect(lambda: self.open_user_download_folder(
                                                    self.user_list_widget.currentRow()))

        self.user_content_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.user_content_list.customContextMenuRequested.connect(self.user_content_list_right_click)
        self.user_content_list.doubleClicked.connect(lambda: self.open_file(self.user_content_list.currentRow()))

        self.item_display_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.item_display_list.customContextMenuRequested.connect(self.item_display_list_right_click)

    def setup(self):
        """
        Sets up parts of the dialog that are dependant upon which user is selected.  It is used as an independent
        function instead of in __init__ because as different users are selected from the user list, these items need to
        be reset and applied to the newly selected user
        """
        if self.current_item_display_list == 'previous_downloads':
            self.setup_previous_downloads_list()
        else:
            self.setup_saved_content_list()
        self.name_downloads_combo.setCurrentText(self.current_user.name_downloads_by)

        self.do_not_edit_checkbox.setChecked(self.current_user.do_not_edit)
        date_limit = self.current_user.date_limit if self.current_user.custom_date_limit is None else \
            self.current_user.custom_date_limit
        if date_limit < 86400:
            date_limit = 86400
        if self.current_user.custom_date_limit is None:
            self.restrict_date_checkbox.setChecked(True)
        elif self.current_user.custom_date_limit == 1:
            self.restrict_date_checkbox.setChecked(False)
        else:
            self.restrict_date_checkbox.setChecked(True)

        self.date_limit_edit.setDateTime(datetime.datetime.fromtimestamp(date_limit))
        self.post_limit_spinbox.setValue(self.current_user.post_limit)
        self.custom_save_path_line_edit.setText(self.current_user.save_path)
        self.download_videos_checkbox.setChecked(self.current_user.download_videos)
        self.download_images_checkbox.setChecked(self.current_user.download_images)
        self.avoid_duplicates_checkbox.setChecked(self.current_user.avoid_duplicates)
        self.user_added_label.setText('User Added On: %s' % datetime.date.strftime(datetime.datetime.fromtimestamp(
                                      self.current_user.user_added), '%m-%d-%Y at %I:%M %p'))
        self.user_downloads_label.setText(str(len(self.current_user.already_downloaded)))

    def setup_previous_downloads_list(self):
        self.current_item_display_list = 'previous_downloads'
        self.item_display_list.clear()
        self.item_display_list_label.setText('Previous Downloads:')
        for item in self.current_user.already_downloaded:
            self.item_display_list.addItem(item)

    def setup_saved_content_list(self):
        self.current_item_display_list = 'saved_content'
        self.item_display_list.clear()
        self.item_display_list_label.setText('Saved Content:')
        self.saved_content_name_dict.clear()
        for key, value in self.current_user.saved_content.items():
            list_item = '%s:  %s' % (value[1], key)
            self.saved_content_name_dict[list_item] = key
            self.item_display_list.addItem(list_item)

    def setup_saved_submission_list(self):
        self.current_item_display_list = 'saved_submissions'
        self.item_display_list.clear()
        self.item_display_list_label.setText('Saved Submissions:')
        for item in self.current_user.saved_submissions:
            self.item_display_list.addItem(item)

    def remove_item_from_item_display_list(self):
        if self.current_item_display_list == 'saved_content':
            self.remove_saved_content()
        else:
            for item in self.item_display_list.selectedItems():
                self.item_display_list.takeItem(self.item_display_list.row(item))
                self.item_display_reddit_object_link_dict[self.current_item_display_list].remove(item.text())

    def remove_saved_content(self):
        for item in self.item_display_list.selectedItems():
            key = self.saved_content_name_dict[item.text()]
            current_content_dict = self.item_display_reddit_object_link_dict[self.current_item_display_list]
            self.item_display_list.takeItem(self.item_display_list.row(item))
            del current_content_dict[key]

    def list_item_change(self):
        self.save_temporary_user()
        self.current_user = self.user_list[self.user_list_widget.currentRow()]
        self.setup()
        if self.stacked_widget.currentIndex() == 1:
            self.setup_user_content_list()

    def save_temporary_user(self):
        """
        Saves changes made to the user list contained in this settings dialog which is a copy of the user list
        in the main GUI window.  This is done to preserve changes when switching users in the dialog list so that if one
        user is changed and then switched to another user, if the user clicks "OK", changes to all subs will be saved
        """
        self.current_user.do_not_edit = self.do_not_edit_checkbox.isChecked()
        if self.current_user.date_limit != int(time.mktime(time.strptime(self.date_limit_edit.text(),
                                                                         '%m/%d/%Y %I:%M %p'))):
            self.current_user.custom_date_limit = int(time.mktime(time.strptime(self.date_limit_edit.text(),
                                                                                '%m/%d/%Y %I:%M %p')))
        if not self.restrict_date_checkbox.isChecked():
            self.current_user.custom_date_limit = 1
        self.current_user.post_limit = self.post_limit_spinbox.value()
        self.current_user.name_downloads_by = self.name_downloads_combo.currentText()
        self.current_user.save_path = "%s%s" % (self.custom_save_path_line_edit.text(), '/' if
                                                not self.custom_save_path_line_edit.text().endswith('/') else '')
        self.current_user.download_videos = self.download_videos_checkbox.isChecked()
        self.current_user.download_images = self.download_images_checkbox.isChecked()
        self.current_user.avoid_duplicates = self.avoid_duplicates_checkbox.isChecked()

    def download_single(self):
        """
        Downloads only the user that is selected.  Emits a signal picked up by the main GUI that runs an instance of
        the RedditExtractor class with a single item user list
        """
        self.download_user_button.setText("Downloading...")
        self.download_user_button.setDisabled(True)
        self.save_temporary_user()
        self.single_download.emit(self.current_user)

    def select_save_path_dialog(self):
        path = self.custom_save_path_line_edit.text() if self.custom_save_path_line_edit != '' else \
                   '%s%s' % (os.path.expanduser('~'), '/Downloads/')
        folder_name = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Save Folder', path))
        if folder_name != '':
            self.custom_save_path_line_edit.setText(folder_name + '/')

    def set_restore_defaults(self):
        self.restore_defaults = True

    def accept(self):
        self.save_temporary_user()
        super().accept()

    def change_page(self):
        if self.stacked_widget.currentIndex() == 0:
            self.page_one_geom = (self.width(), self.height())
            self.change_to_downloads_view()
        else:
            self.page_two_geom = (self.width(), self.height())
            self.change_to_user_settings()

    def change_to_downloads_view(self):
        """
        Changes some settings dialog GUI options that are not relevent to the download page and also changes the page to
        show the downloaded content
        """
        if self.page_two_geom is not None:
            self.resize(self.page_two_geom[0], self.page_two_geom[1])
        self.stacked_widget.setCurrentIndex(1)
        self.view_downloads_button.setText('User Settings')
        self.save_cancel_buton_box.button(QtWidgets.QDialogButtonBox.Ok).setVisible(False)
        self.save_cancel_buton_box.button(QtWidgets.QDialogButtonBox.Cancel).setText('Close')
        self.setup_user_content_list()

    def change_to_user_settings(self):
        """
        Changes GUI options that are not relevent to the settings window and also changes the page to show the user
        settings
        """
        if self.page_one_geom is not None:
            self.resize(self.page_one_geom[0], self.page_one_geom[1])
        self.stacked_widget.setCurrentIndex(0)
        self.view_downloads_button.setText('View Downloads')
        self.save_cancel_buton_box.button(QtWidgets.QDialogButtonBox.Ok).setVisible(True)
        self.save_cancel_buton_box.button(QtWidgets.QDialogButtonBox.Cancel).setText('Cancel')

    def setup_user_content_list(self):
        """Sets up the user content list with the content that is in the currently selected users download directory"""
        self.user_content_list.clear()
        if self.user_content_icons_full_width:
            icon_size = self.user_content_list.width()
        else:
            icon_size = self.user_content_icon_size
        self.user_content_list.setIconSize(QtCore.QSize(icon_size, icon_size))
        if self.show_downloads:
            try:
                self.user_folder = sorted([x for x in os.listdir(self.current_user.save_path)
                                    if os.path.isfile(os.path.join(self.current_user.save_path, x)) and
                                    x.lower().endswith(('.jpg', '.jpeg', '.png'))], key=alphanum_key)
                if len(self.user_folder) > 0:
                    for file in self.user_folder:
                        file_path = '%s%s%s' % (self.current_user.save_path, '/' if not
                                                self.current_user.save_path.endswith('/') else '', file)
                        item = QtWidgets.QListWidgetItem()
                        icon = QtGui.QIcon()
                        pixmap = QtGui.QPixmap(file_path).scaled(QtCore.QSize(500, 500), QtCore.Qt.KeepAspectRatio)
                        icon.addPixmap(pixmap)
                        item.setIcon(icon)
                        item.setText(str(file))
                        self.user_content_list.addItem(item)
                        QtWidgets.QApplication.processEvents()

            except FileNotFoundError:
                self.user_content_list.addItem('No content has been downloaded for this user yet')

    def user_list_widget_right_click(self):
        menu = QtWidgets.QMenu()
        try:
            position = self.user_list_widget.currentRow()
            open_user_foler = menu.addAction('Open User Download Folder')
            open_user_foler.triggered.connect(lambda: self.open_user_download_folder(position))
        except AttributeError:
            Message.no_user_download_folder(self)
        menu.exec(QtGui.QCursor.pos())

    def item_display_list_right_click(self):
        menu = QtWidgets.QMenu()
        button_text = 'Remove Item' if len(self.item_display_list.selectedItems()) < 2 else 'Remove Items'
        open_link = menu.addAction('Open Link')
        remove_item = menu.addAction(button_text)
        menu.addSeparator()
        previous_downloads_list = menu.addAction('Previous Downloads')
        saved_content_list = menu.addAction('Saved Content')
        saved_submissions_list = menu.addAction('Saved Submissions')
        menu_dict = {'previous_downloads': previous_downloads_list,
                     'saved_content': saved_content_list,
                     'saved_submissions': saved_submissions_list}
        open_link.triggered.connect(self.open_link)
        remove_item.triggered.connect(self.remove_item_from_item_display_list)
        previous_downloads_list.triggered.connect(self.setup_previous_downloads_list)
        saved_content_list.triggered.connect(self.setup_saved_content_list)
        saved_submissions_list.triggered.connect(self.setup_saved_submission_list)
        menu_dict[self.current_item_display_list].setEnabled(False)
        menu.exec(QtGui.QCursor.pos())

    def user_content_list_right_click(self):
        self.menu = QtWidgets.QMenu()
        try:
            position = self.user_content_list.currentRow()
            open_file = self.menu.addAction('Open File')
            self.menu.addSeparator()
            self.icons_full_width = self.menu.addAction('Icons Full List Width')
            self.icons_full_width.setCheckable(True)
            self.icon_size_menu = self.menu.addMenu('Icon Size')
            self.icon_size_group = QtWidgets.QActionGroup(self)
            self.icon_size_group.setExclusive(True)

            self.icon_size_extra_small = self.icon_size_menu.addAction('Extra Small')
            self.icon_size_extra_small.setCheckable(True)
            self.icon_size_group.addAction(self.icon_size_extra_small)
            self.icon_size_small = self.icon_size_menu.addAction('Small')
            self.icon_size_small.setCheckable(True)
            self.icon_size_group.addAction(self.icon_size_small)
            self.icon_size_medium = self.icon_size_menu.addAction('Medium')
            self.icon_size_medium.setCheckable(True)
            self.icon_size_group.addAction(self.icon_size_medium)
            self.icon_size_large = self.icon_size_menu.addAction('Large')
            self.icon_size_large.setCheckable(True)
            self.icon_size_group.addAction(self.icon_size_large)
            self.icon_size_extra_large = self.icon_size_menu.addAction('Extra Large')
            self.icon_size_extra_large.setCheckable(True)
            self.icon_size_group.addAction(self.icon_size_extra_large)
            self.set_context_menu_items_checked()

            open_file.triggered.connect(lambda: self.open_file(position))
            self.icons_full_width.triggered.connect(self.set_icons_full_width)
            self.icon_size_extra_small.triggered.connect(lambda: self.set_icon_size(48))
            self.icon_size_small.triggered.connect(lambda: self.set_icon_size(72))
            self.icon_size_medium.triggered.connect(lambda: self.set_icon_size(110))
            self.icon_size_large.triggered.connect(lambda: self.set_icon_size(176))
            self.icon_size_extra_large.triggered.connect(lambda: self.set_icon_size(256))

        except AttributeError:
            print('UserSettingsDialog AttributeError: user_content_right_click')
        self.menu.exec(QtGui.QCursor.pos())

    def open_user_download_folder(self, position):
        selected_user = self.user_list[position]
        open_item = selected_user.save_path
        try:
            self.open_in_system(open_item)
        except AttributeError:
            Message.no_user_selected(self)
        except FileNotFoundError:
            Message.no_user_download_folder(self)

    def open_file(self, position):
        file = '%s%s%s' % (self.current_user.save_path, '/' if not self.current_user.save_path.endswith('/') else
                           '', self.user_folder[position])
        try:
            self.open_in_system(file)
        except (AttributeError, FileNotFoundError):
            pass

    def open_link(self):
        link = self.current_user.already_downloaded[self.item_display_list.currentIndex().row()]
        self.open_in_system(link)

    def open_in_system(self, item):
        if sys.platform == 'win32':
            os.startfile(item)
        else:
            opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
            subprocess.call([opener, item])

    def set_icons_full_width(self):
        self.user_content_icons_full_width = True
        self.user_content_list.setIconSize(QtCore.QSize(self.user_content_list.width(), self.user_content_list.width()))

    def set_icon_size(self, size):
        self.user_content_icons_full_width = False
        self.user_content_icon_size = size
        self.user_content_list.setIconSize(QtCore.QSize(size, size))

    def set_context_menu_items_checked(self):
        if self.user_content_icons_full_width:
            self.icons_full_width.setChecked(True)
        else:
            self.icons_full_width.setChecked(False)
            if self.user_content_icon_size == 48:
                self.icon_size_extra_small.setChecked(True)
            elif self.user_content_icon_size == 72:
                self.icon_size_small.setChecked(True)
            elif self.user_content_icon_size == 110:
                self.icon_size_medium.setChecked(True)
            elif self.user_content_icon_size == 176:
                self.icon_size_large.setChecked(True)
            else:
                self.icon_size_extra_large.setChecked(True)

    def resizeEvent(self, event):
        if self.user_content_icons_full_width:
            self.user_content_list.setIconSize(QtCore.QSize(self.user_content_list.width(),
                                                            self.user_content_list.width()))

    def closeEvent(self, event):
        self.closed = True
        self.settings_manager.user_settings_dialog_geom = self.saveGeometry()
        self.settings_manager.user_content_icons_full_width = self.user_content_icons_full_width
        self.settings_manager.user_content_icon_size = self.user_content_icon_size
        self.settings_manager.current_item_display_list = self.current_item_display_list
        self.settings_manager.save_user_settings_dialog()


# Functions that sort the displayed content in an expected manner
def tryint(s):
    try:
        return int(s)
    except:
        return s


def alphanum_key(s):
    return [tryint(c) for c in re.split('([0-9]+)', s)]
