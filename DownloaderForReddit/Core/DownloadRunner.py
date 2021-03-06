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


import prawcore
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool, QThread
from queue import Queue
from time import time
import logging

from ..Utils import Injector, RedditUtils, VideoMerger
from ..Core.PostFilter import PostFilter
from ..Core import Const
from ..Extractors.Extractor import Extractor


class DownloadRunner(QObject):

    remove_invalid_object = pyqtSignal(object)
    remove_forbidden_object = pyqtSignal(object)
    finished = pyqtSignal()
    downloaded_objects_signal = pyqtSignal(dict)
    failed_download_signal = pyqtSignal(object)
    unfinished_downloads_signal = pyqtSignal(list)
    status_bar_update = pyqtSignal(str)
    setup_progress_bar = pyqtSignal(int)
    update_progress_bar_signal = pyqtSignal()
    stop = pyqtSignal()

    def __init__(self, user_list, subreddit_list, queue, unfinished_downloads_list):
        """
        Class that does the main part of the work for the program.  This class contains the praw instance that is used
        for actually extracting the content from reddit.  When an instance is created all settings parameters must be
        supplied to the instance.  This class also calls the necessary functions of the other classes and completes the
        downloads.

        :param user_list: The actual list of User objects contained in the user ListModel class displayed in the GUI
        :param subreddit_list: The actual list of Subreddit objects contained in the subreddit ListModel class displayed
                               in the GUI. If this class is initialized to only run a user list, this parameter is None
        :param queue: The queue that text is added to in order to update the GUI
        The rest of teh parameters are all configuration options that are set in the settings dialog
        """
        super().__init__()
        self.start_time = time()
        self.logger = logging.getLogger('DownloaderForReddit.%s' % __name__)
        self.settings_manager = Injector.get_settings_manager()
        self._r = RedditUtils.get_reddit_instance()
        self.post_filter = PostFilter()
        self.user_list = [user for user in user_list if user.enable_download] if user_list is not None else None
        self.subreddit_list = [sub for sub in subreddit_list if sub.enable_download] if \
            subreddit_list is not None else None
        self.queue = queue
        self.validated_objects = Queue()
        self.validated_subreddits = []
        self.failed_downloads = []
        self.downloaded_objects = {}
        self.unfinished_downloads = []
        self.user_run = True if self.user_list is not None else False
        self.single_subreddit_run_method = None

        self.unfinished_downloads_list = unfinished_downloads_list
        self.load_undownloaded_content = self.settings_manager.save_undownloaded_content

        self.queued_posts = Queue()
        self.run = True
        self.start_extractor()
        self.start_downloader()

        self.final_download_count = 0

        Const.RUN = True

    def validate_users(self):
        """Validates users and builds a list of all posts to reddit that meet the user provided criteria"""
        self.setup_progress_bar.emit(len(self.user_list) * 2)
        for user in self.user_list:
            if self.run:
                redditor = self._r.redditor(user.name)
                try:
                    test = redditor.fullname
                    self.queue.put("%s is valid" % user.name)
                    user.new_submissions = self.get_submissions(redditor, user)
                    self.validated_objects.put(user)
                    user.check_save_directory()
                    self.update_progress_bar()
                except (prawcore.exceptions.Redirect, prawcore.exceptions.NotFound, AttributeError):
                    self.handle_invalid_reddit_object(user)
                except prawcore.RequestException:
                    self.handle_failed_connection()
                except prawcore.exceptions.Forbidden:
                    self.handle_forbidden_reddit_object(user)
                except:
                    self.handle_unknown_exception(user)
        self.validated_objects.put(None)  # Shuts down the extractor

    def validate_subreddits(self):
        """See validate_users"""
        self.setup_progress_bar.emit(len(self.subreddit_list) * 2)
        for sub in self.subreddit_list:
            if self.run:
                subreddit = self._r.subreddit(sub.name)
                try:
                    test = subreddit.fullname
                    self.queue.put("%s is valid" % sub.name)
                    sub.new_submissions = self.get_submissions(subreddit, sub)
                    self.validated_objects.put(sub)
                    sub.check_save_directory()
                    self.update_progress_bar()
                except (prawcore.exceptions.Redirect, prawcore.exceptions.NotFound, AttributeError):
                    self.handle_invalid_reddit_object(sub)
                except prawcore.RequestException:
                    self.handle_failed_connection()
                except prawcore.exceptions.Forbidden:
                    self.handle_forbidden_reddit_object(sub)
                except:
                    self.handle_unknown_exception(sub)
        self.validated_objects.put(None)

    def validate_users_and_subreddits(self):
        """See validate_users"""
        for sub in self.subreddit_list:
            if self.run:
                try:
                    subreddit = self._r.subreddit(sub.name)
                    self.validated_subreddits.append(subreddit.display_name)
                    self.queue.put('%s is valid' % subreddit.display_name)
                except (prawcore.exceptions.Redirect, prawcore.exceptions.NotFound, AttributeError):
                    self.handle_invalid_reddit_object(sub)
                except prawcore.RequestException:
                    self.handle_failed_connection()

        if self.run:
            for user in self.user_list:
                redditor = self._r.redditor(user.name)
                try:
                    test = redditor.fullname
                    self.queue.put('%s is valid' % user.name)
                    user.new_submissions = self.get_submissions(redditor, user, subreddit_filter=True)
                    self.validated_objects.put(user)
                    user.check_save_directory()
                    self.update_progress_bar()
                except (prawcore.exceptions.Redirect, prawcore.exceptions.NotFound, AttributeError):
                    self.handle_invalid_reddit_object(user)
                except prawcore.RequestException:
                    self.handle_failed_connection()
                except prawcore.exceptions.Forbidden:
                    self.handle_forbidden_reddit_object(user)
                except:
                    self.handle_unknown_exception(user)

        self.validated_objects.put(None)

    def handle_invalid_reddit_object(self, reddit_object):
        """
        Handles logging, output, and cleanup actions that need to happen when a reddit object fails validation.
        :param reddit_object: The reddit object that is not valid.
        :type reddit_object: RedditObject
        """
        self.remove_invalid_object.emit(reddit_object)
        self.queue.put('%s does not exist' % reddit_object.name)
        self.logger.info('Invalid %s detected' % reddit_object.object_type.lower(),
                         extra={'reddit_object': reddit_object.name,
                                'download_count': self.get_download_count(reddit_object)})
        self.update_progress_for_error()

    def get_download_count(self, reddit_object):
        """
        Finds and returns the number of downloads that the supplied reddit object has had during it's lifespan.
        :param reddit_object: A RedditObject for which the number of previous downloads is requested.
        :return: The number of previous downloads that the supplied reddit object has.
        """
        try:
            download_count = len(reddit_object.previous_downloads)
        except:
            download_count = 0
        return download_count

    def handle_failed_connection(self):
        """
        Stops the downloader if a connection to reddit cannot be established.  Also handles logging and output.
        """
        self.run = False
        self.logger.error('Failed to establish a connection to reddit', exc_info=True)
        self.queue.put('Could not establish a connection to reddit\n'
                       'This may mean that reddit is currently unavailable\n'
                       'Please try again later')

    def handle_forbidden_reddit_object(self, reddit_object):
        """
        Handles logging and informing actions necessary when access is attempted for a forbidden reddit object.
        :param reddit_object: A RedditObject for which access is forbidden.
        :type reddit_object: RedditObject
        """
        self.remove_forbidden_object.emit(reddit_object)
        self.queue.put(f'Download from {reddit_object.name} is forbidden')
        self.logger.info(f'Access to {reddit_object.name} is forbidden',
                         extra={'object_type': reddit_object.object_type,
                                'download_count': self.get_download_count(reddit_object)})
        self.update_progress_for_error()

    def handle_unknown_exception(self, reddit_object):
        self.queue.put(f'Unknown error when interacting with {reddit_object.name}')
        self.logger.error('Encountered unknown error when interacting with reddit object',
                          extra={'reddit_object': reddit_object.name}, exc_info=True)
        self.update_progress_for_error()

    def update_progress_for_error(self):
        """
        Updates the progress the appropriate amount of times so that no discrepancy is shown in the number of objects
        iterated through and the progress bar when an error occurs when working with an object and it is not validated
        or extracted.
        """
        self.update_progress_bar()
        self.update_progress_bar()  # Once for validation, once for would be extraction

    def downloads_finished(self):
        """Cleans up objects that need to be changed after the download is complete."""
        time_string = self.calculate_run_time()
        try:
            for sub in self.subreddit_list:
                sub.clear_download_session_data()
        except TypeError:
            pass
        try:
            for user in self.user_list:
                user.clear_download_session_data()
        except TypeError:
            pass
        VideoMerger.merge_videos()
        self.logger.info('Download finished', extra={'download_type': 'User' if self.user_run else 'Subreddit',
                                                     'download_count': self.final_download_count,
                                                     'download_time': time_string})
        self.queue.put('\nFinished\nTime: %s' % time_string)
        if len(self.downloaded_objects) > 0:
            self.send_downloaded_objects()
        self.finished.emit()

    def calculate_run_time(self):
        """
        Calculates and returns the run time of the download runner in a human readable hour, min, sec format.
        :return: The run time in string format
        :rtype: str
        """
        seconds = time() - self.start_time
        min_, sec = divmod(seconds, 60)
        hour, min_ = divmod(min_, 60)

        time_string = ''
        if hour > 0:
            if hour > 1:
                time_string += '%d hours, ' % hour
            else:
                time_string += '%d hour, ' % hour
        if min_ > 0:
            if min_ > 1:
                time_string += '%d mins, ' % min_
            else:
                time_string += '%d min, ' % min_
        time_string += '%d secs' % sec
        return time_string

    def start_extractor(self):
        """
        Initializes an Extractor object, starts a separate thread, and then runs the extractor from the new thread so
        that content can be simultaneously extracted, validated, and downloaded.
        """
        self.extraction_runner = ExtractionRunner(self.queue, self.validated_objects, self.queued_posts, self.user_run)
        self.stop.connect(self.extraction_runner.stop)
        self.extraction_thread = QThread()
        self.extraction_runner.moveToThread(self.extraction_thread)
        self.extraction_thread.started.connect(self.extraction_runner.run_extraction)
        self.extraction_runner.update_progress_bar.connect(self.update_progress_bar)
        self.extraction_runner.send_failed_extract.connect(self.send_failed_extract)
        self.extraction_runner.finished.connect(self.extraction_thread.quit)
        self.extraction_runner.finished.connect(self.extraction_runner.deleteLater)
        self.extraction_thread.finished.connect(self.extraction_thread.deleteLater)
        self.extraction_thread.start()

    def start_downloader(self):
        """
        Initializes a Downloader object, starts a separate thread, and then runds the downloader from the new thread so
        that content can be simultaneously downloaded, extracted and validated.
        :return:
        """
        self.downloader = Downloader(self.queued_posts, self.settings_manager.max_download_thread_count)
        self.stop.connect(self.downloader.stop)
        self.downloader_thread = QThread()
        self.downloader.moveToThread(self.downloader_thread)
        self.downloader_thread.started.connect(self.downloader.download)
        self.downloader.download_count_signal.connect(self.set_final_download_count)
        self.downloader.send_downloaded.connect(self.add_downloaded_object)
        self.downloader.finished.connect(self.downloader_thread.quit)
        self.downloader.finished.connect(self.downloader.deleteLater)
        self.downloader_thread.finished.connect(self.downloader_thread.deleteLater)
        self.downloader_thread.finished.connect(self.downloads_finished)
        self.downloader_thread.start()

    def get_submissions(self, praw_object, reddit_object, subreddit_filter=False):
        """
        Extracts posts from a praw object submission generator if the post passes the PostFilter.
        :param praw_object: A praw object that contains the submission generator.
        :param reddit_object: The User object that holds certain filter settings needed for extracting the posts.
        :param subreddit_filter: Indicates if the submission needs to be filtered based on if its subreddit is in the
                                 validated subreddits list.  Should be set to True when downloading posts from users
                                 made to specific subreddits.  Defaults to False.
        :return: A list of submissions that have been filtered based on the overall settings and the supplied users
                 individual settings.
        """
        posts = []
        for post in self.get_raw_submissions(praw_object, reddit_object.post_limit):
            passes_date_limit = self.post_filter.date_filter(post, reddit_object)
            # stickied posts are taken first when getting submissions by new, even when they are not the newest
            # submissions.  So the first filter pass allows stickied posts through so they do not trip the date filter
            # before more recent posts are allowed through
            if post.stickied or passes_date_limit:
                if passes_date_limit:
                    if (not subreddit_filter or post.subreddit.display_name in self.validated_subreddits) and \
                            self.post_filter.filter_post(post, reddit_object):
                        posts.append(post)
            else:
                break
        return posts

    def get_raw_submissions(self, praw_object, post_limit):
        """
        Gets the raw submission generator from the praw object based on the appropriate settings.
        :param praw_object: Either a praw Redditor or Subreddit object.
        :param post_limit: The post limit from the reddit object that the submissions are for.
        :return: A list generator of submissions from the supplied praw_object.
        """
        if self.user_run:
            posts = praw_object.submissions.new(limit=post_limit)
        else:
            sort = self.get_subreddit_sort_method()
            if sort[0] == 'NEW':
                posts = praw_object.new(limit=post_limit)
            elif sort[0] == 'HOT':
                posts = praw_object.hot(limit=post_limit)
            elif sort[0] == 'RISING':
                posts = praw_object.rising(limit=post_limit)
            elif sort[0] == 'CONTROVERSIAL':
                posts = praw_object.controversial(limit=post_limit)
            else:
                posts = praw_object.top(sort[1].lower(), limit=post_limit)
        return posts

    def get_subreddit_sort_method(self):
        """
        Method used to determine the subreddit sort method.  This is necessary because if a subreddit is downloaded as
        a single, the user can set the sort method for that subreddit only.
        :return: A tuple of the subreddit sort method and the subreddit sort top method
        :rtype: tuple
        """
        if self.single_subreddit_run_method:
            return self.single_subreddit_run_method
        else:
            return self.settings_manager.subreddit_sort_method, self.settings_manager.subreddit_sort_top_method

    def add_downloaded_object(self, obj_dict):
        """
        Adds a new downloaded file path to the downloaded_objects dict under the key of the reddit_object that the file
        was downloaded for.
        :param obj_dict: A dictionary in which the value is a file path of a newly downloaded item and the key is the
                         name of the reddit object for which it was downloaded.
        :type obj_dict: dict
        """
        ro = obj_dict['reddit_object']
        try:
            obj_list = self.downloaded_objects[ro]
            obj_list.append(obj_dict['filename'])
        except KeyError:
            self.downloaded_objects[ro] = [obj_dict['filename']]

    def send_downloaded_objects(self):
        """Emits a signal containing a dictionary of the last downloaded objects."""
        self.downloaded_objects_signal.emit(self.downloaded_objects)

    def send_failed_extract(self, failed_post):
        """
        Emits a signal with the supplied post that failed to extract or download so that the main window can add the
        object to the failed list.
        :param failed_post: The post that failed to extract.
        :type failed_post: Post
        """
        self.failed_download_signal.emit(failed_post)

    def stop_download(self):
        """Stops the download when the user selects to do so."""
        self.queue.put('\nStopped\n')
        Const.RUN = False
        self.run = False
        self.stop.emit()
        self.logger.info('Downloader stopped', extra={'run_time': self.calculate_run_time()})

    def send_unfinished_downloads(self):
        if not self.queued_posts.empty():
            for post in self.queued_posts.get():
                self.unfinished_downloads_signal.emit(post)

    @DeprecationWarning
    def finish_downloads(self):
        """This method is deprecated."""
        self.queued_posts = self.unfinished_downloads_list
        self.final_download_count = len(self.queued_posts)
        self.status_bar_update.emit('Downloaded: 0  of  %s' % self.final_download_count)
        self.start_downloader()

    def skip_user_validation(self):
        """
        Adds the objects in the user list to the validated objects queue.  This method is used for rare circumstances
        where a user has already been validated in order to skip the somewhat expensive process of validation
        """
        for x in self.user_list:
            self.validated_objects.put(x)

    def update_progress_bar(self):
        self.update_progress_bar_signal.emit()

    def set_final_download_count(self, count):
        self.final_download_count = count


class ExtractionRunner(QObject):

    finished = pyqtSignal()
    update_progress_bar = pyqtSignal()
    send_failed_extract = pyqtSignal(object)

    def __init__(self, queue, valid_objects, post_queue, user_extract):
        """
        A class that is extracts downloadable links from container websites who's links have been posted to reddit

        :param queue: The main window queue used to update the GUI output box
        :param valid_objects: Users or subreddits that have been validated
        :param post_queue: The queue where downloadable links are passed to be downloaded by the downloader thread
        """
        super().__init__()
        self.logger = logging.getLogger('DownloaderForReddit.%s' % __name__)
        self.queue = queue
        self.validated_objects = valid_objects
        self.post_queue = post_queue
        self.user_extract = user_extract
        self.extract_count = 0
        self.run = True

    def run_extraction(self):
        """
        Runs the extractor for each user or subreddit object taken from the queue.  This method also handles sending
        update info to the main window and sending content to the downloader.
        """
        self.logger.info('Extraction Runner started')
        while self.run:
            working_object = self.validated_objects.get()
            if working_object is not None:
                working_object.load_unfinished_downloads()
                self.extract(working_object)

                if len(working_object.failed_extracts) > 0:
                    for entry in working_object.failed_extracts:
                        self.send_failed_extract.emit(entry)
                        self.queue.put(entry.format_failed_text())
                if len(working_object.content) > 0:
                    self.queue.put('$$Count %s' % len(working_object.content))
                for post in working_object.content:
                    self.extract_count += 1
                    post.queue = self.queue
                    self.post_queue.put(post)
                self.update_progress_bar.emit()
            else:
                self.run = False
        self.finish()

    def extract(self, reddit_object):
        """
        Creates an extractor object, supplies it with the current reddit object, and runs the extraction process.
        :param reddit_object: The reddit object for which content is to be extracted.
        :type reddit_object: RedditObject
        """
        extractor = Extractor(reddit_object)
        extractor.run()

    def finish(self):
        """
        Cleans up items for the end of the extraction run.
        """
        self.post_queue.put(None)
        self.logger.info('Extractor finished', extra={'extracted_content_count': self.extract_count})
        self.finished.emit()

    def stop(self):
        self.run = False


class Downloader(QObject):

    finished = pyqtSignal()
    download_count_signal = pyqtSignal(int)
    send_downloaded = pyqtSignal(dict)

    def __init__(self, queue, thread_limit):
        """
        Class that spawns the separate download threads.  This is a separate class so it can be moved to its own thread
        and run simultaneously with post extraction.

        :param queue: The download queue in which extracted content is placed
        """
        super().__init__()
        self.logger = logging.getLogger('DownloaderForReddit.%s' % __name__)
        self.queue = queue
        self.download_count = 0
        self.run = True

        self.download_pool = QThreadPool()
        self.download_pool.setMaxThreadCount(thread_limit)

    def download(self):
        """Spawns the download pool threads"""
        self.logger.info('Downloader started')
        while self.run:
            post = self.queue.get()
            if post is not None:
                post.download_complete_signal.complete.connect(self.send_download_dict)
                self.download_pool.start(post)
                self.download_count += 1
            else:
                self.run = False
        self.download_pool.waitForDone()
        self.logger.info('Downloader finished', extra={'download_count': self.download_count})
        self.download_count_signal.emit(self.download_count)
        self.finished.emit()

    def send_download_dict(self, download_dict):
        self.send_downloaded.emit(download_dict)

    def stop(self):
        self.run = False
        self.download_pool.clear()
