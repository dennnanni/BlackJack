# API DOCUMENTATION
_Note that_ when not specified, success responses return `success=True` and error responses return `error` field with
a string describing the error.

## Database module

> **POST** `/users/register`

#### INPUT FIELDS

`UserDatabase` as dictionary.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| username | string | |
| password | string | hashed with SHA256 | 
| salt | string | used to hash password |
| balance | integer | |

#### OUTPUT

- `201 CREATED` 
- `400 BAD REQUEST`
---

> **GET** `/users/salt`

#### INPUT FIELDS

`username` in query string.

#### OUTPUT

- `200 OK` 
    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | salt | string | salt associated with the username |
- `400 BAD REQUEST` or `404 NOT FOUND`
---

> **POST** `/users/login`

Must come after the salt request.

#### INPUT FIELDS

`UserLogin` as dictionary.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| username | string | |
| password | string | hashed with SHA256 using registration salt |

#### OUTPUT

- `200 OK` 
- `400 BAD REQUEST`
---

> **GET** `/users/info`

#### INPUT FIELDS

`username` in query string.

#### OUTPUT

- `200 OK` 
    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | data | `UserInfo` | as dictionary |
- `400 BAD REQUEST` or `404 NOT FOUND`
---

> **GET** `/users/playing`

#### INPUT FIELDS

`username` in query string.

#### OUTPUT

- `200 OK` 
    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | playing | boolean | True if the username appears related to a Game Server in database |
- `400 BAD REQUEST`
---

> **GET** `/servers/load`

#### OUTPUT

- `200 OK` 
    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | data | `List<RegisteredServer>` | as dictionary |
- `500 INTERNAL SERVER ERROR`
---

> **POST** `/servers/register`

#### INPUT FIELDS

`Server` as dictionary.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| ip | string | |
| port | integer | |
| key | string | encrypted with sender's key |

#### OUTPUT

- `201 CREATED` 
- `400 BAD REQUEST` or `500 INTERNAL SERVER ERROR`
---

> **POST** `/servers/results`

#### INPUT FIELDS

List of `Result` object as dictionary.

#### OUTPUT

- `200 OK` 
- `400 BAD REQUEST`

---

> **GET** `/servers/key`

#### INPUT FIELDS

`id` in query string. This refers to the ID assigned to the game server, to retrieve the related key.

#### OUTPUT

- `200 OK` 
    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | encrypted | string | returns the input data encrypted with the transmitted key for validation |
- `400 BAD REQUEST` or `404 NOT FOUND`

## Server interface

> **POST** `/register`

#### INPUT FIELDS

An ecrypted string containing `Server` object as JSON. The encryption should be done with the shared key.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| encrypted | string | the data for registration encrypted with the shared key |

Where `Server` object is in the form:

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| ip | string | |
| port | integer | the port the server wants connection on | 
| key | string | key chosen by the server to communicate with central |

#### OUTPUT

- `201 CREATED`
    An encrypted string containing `RegisteredServer` object as JSON. The encryption is performed the input key. 

    | Field name | Type | Description |
    | ----------- | ----------- | ----------- |
    | encrypted | string | the input data encrypted with the transmitted key for validation |

    Where `RegisteredServer` object adds an id to the `Server` object.
- `400 BAD REQUEST`

> **POST** `/results`

#### INPUT HEADERS:
- `X-Server-ID`: string containing the game server ID.

#### INPUT FIELDS

A JWT token cointaining a list of `Result` as dictionaries.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| token | jwt | list of result as dictionaries  | 

`Result` objects are in form:

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| username | string |  | 
| balance_difference | float | |

    [
        {
            'username': 'alice',
            'balance_difference': 50
        },
        {
            'username': 'bob',
            'balance_difference': -100
        }
    ]

#### OUTPUT

- `201 OK`
- `400 BAD REQUEST`