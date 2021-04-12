# azure-ad
[![Build Status](https://travis-ci.org/sesam-community/azure-ad.svg?branch=master)](https://travis-ci.org/sesam-community/azure-ad)

Sesam - Microsoft Graph API connector that can serve both as a source or sink.
Features:
  * supports the whole Graph API as is
  * offers dedicated URL routes for _user_, _group_ and _planner_ operations. See "URL paths" section below.
  * implements cached authentication
  * streams results for GET requests
  * handles paging implicitly

### Azure AD access

To be able to communicate with Azure AD we need to register an applicaiton in Azure AD and obtain client id and client secret needed for Oauth:

Navigate to https://aad.portal.azure.com -> Dashboard -> App Registrations and create new app

You also need to assign required permissions or/and roles to this app such as `User.ReadWrite.All, Directory.ReadWrite.All, Group.ReadWrite.All`  
read more [here](https://docs.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0&tabs=cs) and [here](https://stackoverflow.com/questions/52626067/microsoft-graph-api-insufficient-privileges-when-trying-to-update-mobilephone)

This app uses Outh2 authentication with either `client_credentials`, `code` or `password` grant type. You need to provide next environment variables:

* `client_id` - from registered application
* `client_secret` - from registered application
* `tenant_id` - Tenant id my be found in Azure AD properties  

in addition for `password` grant type  
* `username` - registered user, couldn't be an invited user or user with 2 factor auth turned on
* `password` - password for this user

To be able to use  authorization code flow you need to navigate first to `/auth` endpoint and perform authentication as a user.
All next requests will then use acquired token and refresh it if needed by using refresh_token.  

**Remember to add correct `redirect_uri` to application properties in Azure.**

By default `client_credentials` schema used for every request, to use `password` schema add query parameter `auth` with value `user` to request.

You may control MS Graph API version with environmental variable `API_VERSION`


By default all queries executed with `odata.metadata=minimal`. This behavior may be changed by using  environmental variable `ODATA_METADATA` (available values: `none`, `minimal`, `full`).


### URL paths

 * **/datasets/user/entities** : methods=['GET'], get users
 * **/datasets/group/entities** : methods=['GET'], get groups
 * **/datasets/<path:kind>/entities** : methods=['GET'], get objects of given type from MS graph API
 * **/planner/plans/entities** , methods=['GET'], get all plans from Microsoft Planner service
 * **/planner/tasks/entities** , methods=['GET'], get all tasks from Microsoft Planner service
 * **/datasets/user** : methods=['POST'], create or update or delete or disable users. Performs create/update operation based on the presence of _id_ field or encountering 'resource exists' error; performs disable/delete based on \_deleted value combined with query params.  
      Query params:
    * _force_delete_ : set to 'true' to delete user instead of disabling
 * **/datasets/group** : methods=['POST'], same as /datasets/user handler but for _group_ object
 * **/graphapi/&lt;path:path&gt;** : methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], Generic route for MS graph API. Call it in the same way as you would call the graph API directly except that you don't need to think about authorization. Returns 200 for all GET requests even if error occurs, and for all successful calls. Returns 500 for erronous calls.
 * **/auth** : methods=['GET'], signs in user interactively by using Microsoft login page

### System setup

```json
{
  "_id": "ms-graph-test-service",
  "type": "system:microservice",
  "docker": {
    "environment": {
      "LOG_LEVEL": "DEBUG|INFO|WARNING|ERROR",
      "client_id": "<client id>",
      "client_secret": "<client secret>",
      "tenant_id": "<azure tenant id>"
    },
    "image": "<docker image>",
    "port": 5000
  },
  "verify_ssl": true
}
```

### Setup for "fetch" pipe to retrieve Azure AD users

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "json",
    "system": "ms-graph-test-service",
    "url": "/datasets/users/entities"
  }
}

```

### Setup for "fetch" pipe to retrieve another resources available through MS Graph API
**Here used to fetch lists for given Sharepoint site**  
*you will need `Sites.Read.All` permission to perform this request*

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "json",
    "system": "ms-graph-test-service",
    "url": "/datasets/sites/<sharepoint site id>/lists/entities"
  }
}

```

### Setup for "fetch" pipe to retrieve Microsoft Planner plans through MS Graph API
*Some of groups may throw 403 exception which is logged but swallowed so pipe don't receive any error*
*Check system log after fetching plans to be sure if everything is ok*

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "json",
    "system": "ms-graph-test-service",
    "url": "/planner/plans/entities"
  }
}

```


### Setup for "fetch" pipe to retrieve Microsoft Planner tasks through MS Graph API
*Some of groups may throw 403 exception which is logged but swallowed so pipe don't receive any error*
*Check system log after fetching plans to be sure if everything is ok*

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "json",
    "system": "ms-graph-test-service",
    "url": "/planner/tasks/entities"
  }
}

```

### Setup for "create/update" pipe

You need to supply correct representation of user. There are different requirements when you create or update an user.  
For example `passwordProfile` must be supplied to create user but not allowed when you update user.  
Another very important attribute is `userPrincipalName` -  By convention, this should map to the user's email name. The general format is alias@domain, where domain must be present in the tenant’s collection of verified domains.   

Read more [here](https://docs.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-beta)

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "dataset",
    "dataset": "<source dataset name>"
  },
  "sink": {
    "type": "json",
    "system": "<sink system id>",
    "url": "/datasets/user"
  },
  "transform": {
    "type": "dtl",
    "rules": {
      "default": [
        ["copy", "*"],
        ["add", "jobTitle", "programmer"]
      ]
    }
  }
}

```

```json
{
  "_id": "<pipe id>",
  "type": "pipe",
  "source": {
    "type": "dataset",
    "dataset": "<source dataset name>"
  },
  "sink": {
    "type": "json",
    "system": "<sink system id>",
    "url": "/graphapi/applications"
  },
  "transform": {
    "type": "dtl",
    "rules": {
      "default": [
        ["add", "displayName", "Display name"]
      ]
    }
  }
}

```
