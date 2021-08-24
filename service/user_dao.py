import logging

from dao_helper import get_all_objects, make_request, GRAPH_URL, is_object_already_exists_exception, \
    clear_sesam_attributes, stream_as_json

RESOURCE_PATH = '/users/'


def sync_user_array(user_data_array: list, do_force_delete=False) -> None:
    """
    Function to synchronize user array from Sesam into Azure Active Directory
    This function will try to create user first and update it if create operation failed
    This function will also disable users with _deleted property = true or delete them if force_delete is true
    :param user_data_array: array of user objects
    :return: nothing if everything is OK
    """

    def __try_create(user_data: dict) -> None:
        """
        Internal function to create user
        :param user_data: json object with user details
        :return: void
        """
        logging.info(f'trying to create user {user_data.get("userPrincipalName")}')
        make_request(f'{GRAPH_URL}{RESOURCE_PATH}', 'POST', user_data)
        logging.info(f'user {user_data.get("userPrincipalName")} created successfully')

    def __try_update(user_data: dict) -> None:
        """
        Internal function to update user
        Update user with passwordProfile is not possible without Directory.AccessAsUser.All
        which is not exist in "application" permission so we need to remove this part if exist
        :param user_data: json object with user details, must contain user identifier
        (id or userPrincipalName property)
        :return: void
        """
        user_id = user_data['id'] if user_data.get('id') else user_data['userPrincipalName']

        if not user_id:
            raise Exception("Couldn't find id for user, at least id or userPrincipalName needed")
        # we can't and don't need to update user password when syncing user with Azure
        if user_data.get('passwordProfile'):
            del user_data['passwordProfile']

        logging.info(f'trying to update user {user_id}')
        make_request(f'{GRAPH_URL}{RESOURCE_PATH}{user_id}', 'PATCH', user_data)
        logging.info(f'user {user_id} updated successfully')

    def __try_delete(user_data: dict, do_force_delete) -> None:
        """
        Internal function to disable/delete user
        If force_delete is on, delete user for good, otherwise disable user account by setting accountEnabled = false
        :param user_data: json object with user details, must contain user identifier
        (id or userPrincipalName property)
        :return: void
        """
        user_id = user_data['id'] if user_data.get('id') else user_data['userPrincipalName']
        if not user_id:
            raise Exception("Couldn't find id for user, at least id or userPrincipalName needed")

        logging.info(f'trying to disable/delete user {user_id}')
        if do_force_delete:
            make_request(f'{GRAPH_URL}{RESOURCE_PATH}{user_id}', 'DELETE')
        else:
            make_request(f'{GRAPH_URL}{RESOURCE_PATH}{user_id}', 'PATCH', {'accountEnabled': False})
        logging.info(f'user {user_id} disabled/deleted successfully')

    for user in user_data_array:
        if '_deleted' in user and user['_deleted']:
            __try_delete(user, do_force_delete)
            continue

        user = clear_sesam_attributes(user)
        try:
            if 'id' not in user:
                __try_create(user)
            else:
                __try_update(user)
        except Exception as e:
            if is_object_already_exists_exception(e):
                __try_update(user)
            else:
                raise Exception from e


def get_all_users(delta=None, params=None):
    """
    Fetch and stream back users from Azure AD via MS Graph API
    :param delta: delta token from last request
    :return: generated JSON output with all fetched users
    """
    yield from stream_as_json(get_all_objects(f'{RESOURCE_PATH}delta', delta, params=params))
