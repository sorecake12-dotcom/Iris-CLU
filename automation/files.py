"""
IRIS AI - Independent File System Automation Interface
Wraps core file operations for file_engine.
"""

from file_engine import file_engine


def create_file(path_keyword: str, name: str, content: str = "") -> str:
    return file_engine.create_file(path_keyword, name, content)


def create_folder(path_keyword: str, name: str) -> str:
    return file_engine.create_folder(path_keyword, name)


def read_file(path_keyword: str, name: str, max_lines: int = 50) -> str:
    return file_engine.read_file(path_keyword, name, max_lines)


def delete_item(path_keyword: str, name: str, confirmed: bool = False) -> str:
    return file_engine.delete_item(path_keyword, name, confirmed)


def compress_item(path_keyword: str, name: str) -> str:
    return file_engine.compress_item(path_keyword, name)


def search_files(query: str = "", location: str = "home", file_type: str = "") -> list:
    return file_engine.search_files(query, location, file_type)
