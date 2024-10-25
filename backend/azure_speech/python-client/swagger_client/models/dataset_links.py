# coding: utf-8

"""
    Speech Services API version 3.2

    Speech Services API version 3.2.  # noqa: E501

    OpenAPI spec version: 3.2
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


import pprint
import re  # noqa: F401

import six

from swagger_client.configuration import Configuration


class DatasetLinks(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """

    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'files': 'str',
        'commit_blocks': 'str',
        'list_blocks': 'str',
        'upload_blocks': 'str'
    }

    attribute_map = {
        'files': 'files',
        'commit_blocks': 'commitBlocks',
        'list_blocks': 'listBlocks',
        'upload_blocks': 'uploadBlocks'
    }

    def __init__(self, files=None, commit_blocks=None, list_blocks=None, upload_blocks=None, _configuration=None):  # noqa: E501
        """DatasetLinks - a model defined in Swagger"""  # noqa: E501
        if _configuration is None:
            _configuration = Configuration()
        self._configuration = _configuration

        self._files = None
        self._commit_blocks = None
        self._list_blocks = None
        self._upload_blocks = None
        self.discriminator = None

        if files is not None:
            self.files = files
        if commit_blocks is not None:
            self.commit_blocks = commit_blocks
        if list_blocks is not None:
            self.list_blocks = list_blocks
        if upload_blocks is not None:
            self.upload_blocks = upload_blocks

    @property
    def files(self):
        """Gets the files of this DatasetLinks.  # noqa: E501

        The location to get all files of this entity. See operation \"Datasets_ListFiles\" for more details.  # noqa: E501

        :return: The files of this DatasetLinks.  # noqa: E501
        :rtype: str
        """
        return self._files

    @files.setter
    def files(self, files):
        """Sets the files of this DatasetLinks.

        The location to get all files of this entity. See operation \"Datasets_ListFiles\" for more details.  # noqa: E501

        :param files: The files of this DatasetLinks.  # noqa: E501
        :type: str
        """

        self._files = files

    @property
    def commit_blocks(self):
        """Gets the commit_blocks of this DatasetLinks.  # noqa: E501

        The location to commit the list of blocks when uploading a dataset using blocks. See operation \"Datasets_CommitBlocks\" for more details.  # noqa: E501

        :return: The commit_blocks of this DatasetLinks.  # noqa: E501
        :rtype: str
        """
        return self._commit_blocks

    @commit_blocks.setter
    def commit_blocks(self, commit_blocks):
        """Sets the commit_blocks of this DatasetLinks.

        The location to commit the list of blocks when uploading a dataset using blocks. See operation \"Datasets_CommitBlocks\" for more details.  # noqa: E501

        :param commit_blocks: The commit_blocks of this DatasetLinks.  # noqa: E501
        :type: str
        """

        self._commit_blocks = commit_blocks

    @property
    def list_blocks(self):
        """Gets the list_blocks of this DatasetLinks.  # noqa: E501

        The location to list the already uploaded blocks of this entity when uploading a dataset using blocks. See operation \"Datasets_GetBlocks\" for more details.  # noqa: E501

        :return: The list_blocks of this DatasetLinks.  # noqa: E501
        :rtype: str
        """
        return self._list_blocks

    @list_blocks.setter
    def list_blocks(self, list_blocks):
        """Sets the list_blocks of this DatasetLinks.

        The location to list the already uploaded blocks of this entity when uploading a dataset using blocks. See operation \"Datasets_GetBlocks\" for more details.  # noqa: E501

        :param list_blocks: The list_blocks of this DatasetLinks.  # noqa: E501
        :type: str
        """

        self._list_blocks = list_blocks

    @property
    def upload_blocks(self):
        """Gets the upload_blocks of this DatasetLinks.  # noqa: E501

        The location to upload blocks to when uploading a dataset using blocks. See operation \"Datasets_UploadBlock\" for more details.  # noqa: E501

        :return: The upload_blocks of this DatasetLinks.  # noqa: E501
        :rtype: str
        """
        return self._upload_blocks

    @upload_blocks.setter
    def upload_blocks(self, upload_blocks):
        """Sets the upload_blocks of this DatasetLinks.

        The location to upload blocks to when uploading a dataset using blocks. See operation \"Datasets_UploadBlock\" for more details.  # noqa: E501

        :param upload_blocks: The upload_blocks of this DatasetLinks.  # noqa: E501
        :type: str
        """

        self._upload_blocks = upload_blocks

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(DatasetLinks, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, DatasetLinks):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, DatasetLinks):
            return True

        return self.to_dict() != other.to_dict()
