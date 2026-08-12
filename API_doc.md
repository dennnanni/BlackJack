# API DOCUMENTATION
_Note that_ when not specified, success responses return `success=True` and error responses return `error` field with
a string describing the error.

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