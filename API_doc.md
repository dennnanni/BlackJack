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

`GameServer` as dictionary.

| Field name | Type | Description |
| ----------- | ----------- | ----------- |
| ip | string | |
| port | integer | |
| key | string | encrypted with sender's key |

#### OUTPUT

- `201 CREATED` 
- `400 BAD REQUEST` or `500 INTERNAL SERVER ERROR`
---

