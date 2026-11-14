"""
The version of lxml that the XML and HTML parsers record.
"""

from lxml import etree


def lxml_version() -> str:
    """
    Name the versions of lxml and of the libxml2 it uses.

    Returns:
        A version such as ``6.1.3 (libxml2 2.14.6)``.
    """
    libxml2 = ".".join(str(number) for number in etree.LIBXML_VERSION)

    return f"{etree.__version__} (libxml2 {libxml2})"
