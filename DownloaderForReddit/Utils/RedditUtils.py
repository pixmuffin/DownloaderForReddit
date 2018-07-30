import praw

from Core.Post import Post
from version import __version__


reddit_instance = None


def get_reddit_instance():
    global reddit_instance
    if not reddit_instance:
        reddit_instance = praw.Reddit(user_agent='python:DownloaderForReddit:%s (by /u/MalloyDelacroix)' % __version__,
                              client_id='frGEUVAuHGL2PQ', client_secret=None)
    return reddit_instance


def convert_praw_post(praw_post):
    """
    A utility function that converts a praw submission object into a Post object which can be marshaled.  The method
    first checks to make sure that the supplied post is an instance of a praw submission object.
    """
    if isinstance(praw_post, praw.models.reddit.submission.Submission):
        return Post(praw_post.url, praw_post.author.name, praw_post.title, praw_post.subreddit.display_name,
                    praw_post.created, domain=praw_post.domain)
    else:
        return praw_post
