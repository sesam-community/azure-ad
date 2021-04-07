#!/usr/bin/env python3

import logging
import datetime
import os
import json
import uuid
from flask import Flask, Response, request as r, redirect, session
from requests.exceptions import HTTPError

from auth_helper import get_authorize_url, get_token_with_auth_code, add_token_to_cache
from plan_dao import get_plans, get_tasks
from str_utils import str_to_bool
from user_dao import sync_user_array, get_all_users
from group_dao import sync_group_array, get_all_groups
from dao_helper import init_dao, get_all_objects, init_dao_on_behalf_on, stream_as_json, make_request, GRAPH_URL, ALLOWED_METHODS
from logger_helper import log_request

env = os.environ.get

APP = Flask(__name__)
LOG_LEVEL = env('LOG_LEVEL', "INFO")
PORT = int(env('PORT', '5000'))
CT = 'application/json'

SUPPORTS_SINCE = str_to_bool(env('SUPPORTS_SINCE', 'false'))

# used to encrypt user sessions
APP.secret_key = uuid.uuid4().bytes


@APP.route('/datasets/user/entities', methods=['GET'])
@log_request
def list_users():
    """
    Endpoint to fetch all users from Azure AD via MS graph API
    :request_argument since - delta token returned from last request (if exist)
    :return: JSON array with fetched users
    """
    init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    return Response(get_all_users(r.args.get('since')), content_type=CT)


@APP.route('/datasets/group/entities', methods=['GET'])
@log_request
def list_groups():
    """
    Endpoint to fetch all groups from Azure AD via MS graph API
    :request_argument since - delta token returned from last request (if exist)
    :return: JSON array with fetched groups
    """
    init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    return Response(get_all_groups(r.args.get('since')), content_type=CT)


@APP.route('/datasets/<path:kind>/entities', methods=['GET'])
@log_request
def list_objects(kind):
    """
    Endpoint to fetch all objects of given type from MS graph API
    :request_argument since - delta token returned from last request (if exist)
    :return: JSON array with fetched groups
    """
    if r.args.get('auth') and r.args.get('auth') == 'user':
        init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                              env('password'))
    else:
        init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    return Response(
        stream_as_json(get_all_objects(f'/{kind}/{"delta" if SUPPORTS_SINCE else ""}', r.args.get('since'))),
        content_type=CT)


@APP.route('/planner/plans/entities', methods=['GET'])
@log_request
def list_all_plans():
    """
    Endpoint to list all plans from Microsoft Planner service
    :return:
    """
    if r.args.get('auth') and r.args.get('auth') == 'user':
        init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                              env('password'))
    else:
        init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    return Response(stream_as_json(get_plans(get_all_objects('/groups/'))), r.args.get('since'), content_type=CT)


@APP.route('/planner/tasks/entities', methods=['GET'])
@log_request
def list_all_tasks():
    if r.args.get('auth') and r.args.get('auth') == 'user':
        init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                              env('password'))
    else:
        init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    return Response(stream_as_json(get_tasks(get_plans(get_all_objects('/groups/')))), content_type=CT)


@APP.route('/datasets/user', methods=['POST'])
@log_request
def post_users():
    """
    Endpoint to synchronize users from Sesam into Azure AD
    :return: 200 empty response if everything OK
    """
    try:
        if r.args.get('auth') and r.args.get('auth') == 'user':
            init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                                  env('password'))
        else:
            init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
        sync_user_array(json.loads(r.data))
        response = Response('')
    except HTTPError as error:
        logging.exception(error)
        response = Response(error.response.text, content_type=CT, status=error.response.status_code)
    return response

@APP.route('/datasets/group', methods=['POST'])
@log_request
def post_groups():
    """
    Endpoint to synchronize groups from Sesam into Azure AD
    :return: 200 empty response if everything OK
    """
    try:
        if r.args.get('auth') and r.args.get('auth') == 'user':
            init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                                  env('password'))
        else:
            init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
        sync_group_array(json.loads(r.data))
        response = Response('')
    except HTTPError as error:
        logging.exception(error)
        response = Response(error.response.text, content_type=CT, status=error.response.status_code)

    return response

@APP.route('/graphapi/<path:path>', methods=ALLOWED_METHODS)
@log_request
def generic_graph_api_request(path=None):
    """
    Generic Endpoint to call Microsoft Graph API.
    Any request in Microsoft Graph API can be issued here.
    :return: 200 for successful GET requests
             200 and malformed json for erronous GET requests
             code and response from graghapi for other cases
    """
    if r.args.get('auth') and r.args.get('auth') == 'user':
        init_dao_on_behalf_on(env('client_id'), env('client_secret'), env('tenant_id'), env('username'),
                              env('password'))
    else:
        init_dao(env('client_id'), env('client_secret'), env('tenant_id'))
    try:
        if r.method.lower() == 'get':
            response = Response(stream_as_json(get_all_objects(f'/{path}')), content_type=CT, status=200)
        else:
            url=f'{GRAPH_URL}/{path}'
            data=json.loads(r.data) if r.data else None

            response = Response(json.dumps(make_request(url=url, method=r.method, data=data)), content_type=CT, status=200)
    except HTTPError as error:
        logging.exception(error)
        response = Response(error.response.text, content_type=CT, status=error.response.status_code)

    return response

@APP.route('/auth', methods=['GET'])
@log_request
def auth_user():
    """
    Endpoint to sign in user interactively by using Microsoft login page
    :return:
    """
    state = str(datetime.datetime.now().timestamp()) if 'state' not in session else session['state']
    tenant = env('tenant_id')
    client_id = env('client_id')
    client_secret = env('client_secret')
    redir_url = env('redirect_url')

    if not r.args.get('code'):
        session['state'] = state
        return redirect(get_authorize_url(tenant, client_id, state, redir_url))
    else:
        code = r.args.get('code')
        returned_state = r.args.get('state')
        if state != returned_state:
            print(state)
            print(returned_state)
            raise SystemError("Response state doesn't match request state")

        token = get_token_with_auth_code(tenant, client_id, client_secret, code, redir_url)
        if 'access_token' in token:
            add_token_to_cache(client_id, tenant, token)
            return Response(json.dumps({'status': 'ok', 'message': 'token acquired'}), content_type=CT)
        else:
            raise ValueError("token response malformed")


if __name__ == '__main__':
    """
    Application entry point
    """
    logging.basicConfig(level=logging.getLevelName(LOG_LEVEL))

    IS_DEBUG_ENABLED = True if logging.getLogger().isEnabledFor(logging.DEBUG) else False

    if IS_DEBUG_ENABLED:
        APP.run(debug=IS_DEBUG_ENABLED, host='0.0.0.0', port=PORT)
    else:
        import cherrypy

        cherrypy.tree.graft(APP, '/')
        cherrypy.config.update({
            'environment': 'production',
            'engine.autoreload_on': True,
            'log.screen': False,
            'server.socket_port': PORT,
            'server.socket_host': '0.0.0.0',
            'server.thread_pool': 10,
            'server.max_request_body_size': 0
        })

        cherrypy.engine.start()
        cherrypy.engine.block()
