from DownloaderForReddit.Core.Content import Content
from DownloaderForReddit.Core.Post import Post
from DownloaderForReddit.Core.RedditObjects import User, Subreddit


def get_blank_user():
    user = User('v0.0.0', 'JohnEveryman', 'C:/Users/Gorgoth/Downloads/', 10, True, True, True, 'INCLUDE',
                'Image/Album Id', 86400)
    return user


def get_blank_subreddit():
    subreddit = Subreddit('v0.0.0', 'SomeSub', 'C:/Users/Gorgoth/Downloads', 10, True, True, True, 'INCLUDE',
                          'Image/Album Id', 86400)
    return subreddit


def get_user_with_single_content():
    user = get_blank_user()
    user.content.append(get_downloadable_single_content(user))
    return user


def get_user_with_multiple_content():
    user = get_blank_user()
    user.content = get_downloadable_content_list(user)
    return user


def get_downloadable_single_content(object_):
    sub_method = 'Subreddit Name' if object_.object_type == 'SUBREDDIT' else None
    return create_content(object_, 0, sub_method)


def get_downloadable_content_list(object_):
    sub_method = 'Subreddit Name' if object_.object_type == 'SUBREDDIT' else None
    return [create_content(object_, x, sub_method) for x in range(5)]


def get_non_downloadable_single_content(object_):
    sub_method = 'Subreddit Name' if object_.object_type == 'SUBREDDIT' else None
    return create_content(object_, 0, sub_method)


def create_content(object_, number, sub_method):
    content = Content('http://test-url.com/FluffyKitten.jpg', object_.name, 'Fake Post', 'aww', '4921k', number, '.jpg',
                      object_.save_directory, sub_method, 1521473630, False)
    return content


def get_generic_mock_post():
    author = 'Gorgoth'
    title = 'Picture(s)'
    subreddit = 'Pics'
    created = 1521473630
    return Post(None, author, title, subreddit, created)


def get_unsupported_direct_post():
    post = get_generic_mock_post()
    post.url = 'https://invalid_site.com/image/3jfd9nlksd.jpg'
    return post


def get_mock_post_imgur():
    post = get_generic_mock_post()
    post.url = 'https://imgur.com/fb2yRj0'
    return post


def get_mock_post_gfycat():
    post = get_generic_mock_post()
    post.url = 'https://gfycat.com/KindlyElderlyCony'
    return post

def get_mock_post_gfycat_direct():
    post = get_generic_mock_post()
    post.url = 'https://giant.gfycat.com/KindlyElderlyCony.webm'
    return post

def get_mock_post_gfycat_tagged():
    post = get_generic_mock_post()
    post.url = 'https://gfycat.com/anchoredenchantedamericanriverotter-saturday-exhausted-weekend-kitten-pissed'
    return post

def get_mock_post_vidble_direct():
    post = get_generic_mock_post()
    post.url = 'https://vidble.com/XOwqxH6Xz9.jpg'
    return post

def get_mock_post_vidble():
    post = get_generic_mock_post()
    post.url = 'https://vidble.com/XOwqxH6Xz9'
    return post


def get_mock_post_vidible_album():
    post = get_generic_mock_post()
    post.url = 'https://vidble.com/album/3qY9KtlA'
    return post


def get_mock_post_reddit_video():
    post = MockPrawPost('https://v.redd.it/lkfmw864od1971', 'Gorgoth', 'Reddit Video Broh', 'PublicFreakout',
                        1521473630, 3500, False, False)
    return post


class MockPrawPost:

    def __init__(self, url=None, author=None, title=None, subreddit=None, created=None, score=None, over_18=None,
                 is_video=False, crosspost_parent=None, media=None, stickied=False):
        self.url = url
        self.author = author
        self.title = title
        self.subreddit = subreddit
        self.created = created
        self.score = score
        self.over_18 = over_18
        self.is_video = is_video
        self.crosspost_parent = crosspost_parent
        self.media = media
        self.stickied = stickied

        self.id = 'abcde'
        self.domain = 'reddit'


class MockPrawSubreddit:

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.display_name = self.name
