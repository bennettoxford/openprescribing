import datetime
import hashlib
import mmap
import os.path
import sqlite3


def generate_filename(sqlite_path):
    """
    Generates a name for the supplied MatrixStore file which includes various
    details about it

    The name is structured so that sorting lexically gives the file with the
    latest build of the latest data. It includes a hash of the file's contents
    which can be used as a cache key and also for de-duplication (so it's easy
    to see if rebuilding a file has resulted in any change to the data).
    """
    last_modified = datetime.datetime.utcfromtimestamp(os.path.getmtime(sqlite_path))
    max_date = get_max_date_from_file(sqlite_path)
    hash_str = hash_file(sqlite_path)
    return "matrixstore_{max_date}_{modified}_{hash}.sqlite".format(
        max_date=max_date.strftime("%Y-%m"),
        modified=last_modified.strftime("%Y-%m-%d--%H-%M"),
        hash=hash_str[:16],
    )


def get_max_date_from_file(sqlite_path):
    """
    Return the maximum date stored in a MatrixStore file
    """
    connection = sqlite3.connect(sqlite_path)
    max_date = connection.execute("SELECT MAX(date) FROM date").fetchone()[0]
    connection.close()
    return parse_date(max_date)


def parse_date(date_str):
    """
    Return `datetime.date` from string in `YYYY-MM-DD` format
    """
    return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()


def hash_file(filename):
    """
    Return the hexadecimal MD5 hash of the given file
    """
    # Memory mapping appears to be the easiest and most efficient way to hash
    # large files in Python
    with open(filename, "rb") as f:
        mmapped_file = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            hashobj = hashlib.md5(mmapped_file)
        finally:
            mmapped_file.close()
    return hashobj.hexdigest()
