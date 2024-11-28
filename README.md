## APIs Documentation

This document outlines the core endpoints of the system, including their functionality, rate-limiting information, and necessary validation.

### General Authentication Flow

All API requests, except for `/public-api/OAuth/token` and `/public-api/OAuth/token/refresh`, require a valid OAuth2 Bearer token for authentication. This token must be included in the request header as `Authorization: Bearer {token}`.

### Rate Limiting

- **General Rate Limiting**: The rate limits vary per endpoint but are globally enforced using Flask-Limiter and the `@limits` decorator. 
- **Global Limit**: Requests are capped at 200 per day and 50 per hour for each unique client.
- **Specific Endpoint Limits**:
  - `/public-api/OAuth/token`: 4 requests per hour per client.
  - `/public-api/OAuth/token/refresh`: 4 requests per hour per client, with backoff for rate-limiting exceptions.
  - `/public-api/meters/retrieve-readings`: 10 requests per minute.

## Endpoints

### `/public-api/OAuth/token` (POST)

**Description**:  
This endpoint allows clients to authenticate and obtain a new OAuth2 token.

**Rate Limit**:  
4 requests per hour per client.

**Request Parameters**:
- `client_id` (string): The unique identifier for the client.
- `client_secret` (string): The client’s secret key.
- `grant_type` (string): Optional. Defaults to `client_credentials`.

**Response**:
- **Success (200)**: A new OAuth2 token is returned.
- **Error (400)**: Invalid client ID or secret.
- **Error (401)**: Client authentication failed.

**Example**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### `/public-api/OAuth/token/refresh` (POST)

**Description**:  
This endpoint allows clients to refresh an expired token by providing a valid refresh token.

**Rate Limit**:  
4 requests per hour per client, with exponential backoff on rate limit exceptions.

**Request Parameters**:
- `client_id` (string): The unique identifier for the client.
- `refresh_token` (string): The refresh token obtained earlier.

**Response**:
- **Success (200)**: A new OAuth2 token is returned.
- **Error (400)**: Invalid refresh token.
- **Error (429)**: Rate limit exceeded.

**Example**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### `/public-api/meters/bulk-retrieve-readings` (POST)

**Description**:  
This endpoint retrieves bulk meter readings for specified logical devices within a division and for a specific date. The request is logged for auditing purposes.

**Rate Limit**:  
10 requests per minute.

**Request Parameters**:
- `logical_device_names` (array of strings): A list of logical device names to retrieve readings for.
- `division_id` (string): The division identifier (e.g., `DD1`, `DD2`).
- `date` (string): The date for which the readings are requested. Must be in `YYYY-MM-DD` format, and the day should be the first of the month.

**Response**:
- **Success (200)**: A list of readings for each logical device.
- **Error (400)**: Invalid or missing parameters (e.g., invalid device name, unsupported division, etc.).
- **Error (500)**: Internal server error.

**Example**:
```json
{
  "result": [
    {
      "logical_device_name": "device1",
      "reading_status": "success",
      "data": {...}
    },
    {
      "logical_device_name": "device2",
      "reading_status": "error",
      "message": "Device not found"
    }
  ]
}
```

### `/public-api/meters/retrieve-readings` (POST)

**Description**:  
This endpoint retrieves meter readings for a given logical device within a specified date range.

**Rate Limit**:  
10 requests per minute.

**Request Parameters**:
- `logical_device_name` (string): The name of the logical device.
- `divisionID` (string): The division identifier (e.g., `DD1`, `DD2`).
- `start_date` (string): The start date for the readings in `YYYY-MM-DD` format.
- `end_date` (string): The end date for the readings in `YYYY-MM-DD` format.

**Response**:
- **Success (200)**: Meter readings for the requested device and date range.
- **Error (400)**: Missing or invalid parameters.
- **Error (500)**: Internal server error.

**Example**:
```json
{
  "result": [
    {
      "date": "2024-10-01",
      "reading": 123.45
    },
    {
      "date": "2024-10-02",
      "reading": 127.56
    }
  ]
}
```

## Error Codes

- `400 Bad Request`: The client sent an invalid request (e.g., missing parameters, invalid data format).
- `401 Unauthorized`: The client failed to authenticate.
- `403 Forbidden`: The client does not have permission to access the resource.
- `429 Too Many Requests`: The client has exceeded the allowed rate limits.
- `500 Internal Server Error`: An unexpected error occurred on the server.

## Token and Permission Validation

Tokens are validated using OAuth2 standards. If a client is missing or has an invalid token, the server will respond with an error indicating the problem.

**Permission Check**:  
Each protected endpoint checks the token's permissions to ensure the client is authorized to access the requested resource. If a client lacks the necessary permissions for an endpoint, a `403 Forbidden` error is returned.
