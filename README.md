# **API Documentation**

## Introduction

This API allows clients to interact with the system for retrieving meter readings and other related data. The API uses OAuth2 for authentication and enforces rate limits to ensure fair usage.

## Authentication

All API requests, except those related to token generation (`/public-api/OAuth/token`), require a valid OAuth2 bearer token. This token should be included in the `Authorization` header of your request:

```http
Authorization: Bearer {token}
```

You can obtain an OAuth2 token via the `/public-api/OAuth/token` endpoint.

## Base URL

- **Bulk Report Endpoints**: `/bulkreport`
- **Ordinary Report Endpoints**: `/ordinaryreport`
- **General API**: `/`

## Rate Limits

- **General Rate Limiting**: Clients are allowed a maximum of 200 requests per day and 50 requests per hour.
- **Specific Endpoint Limits**:
  - **OAuth token generation**: 4 requests per hour.
  - **Meter readings**: 10 requests per minute for both bulk and ordinary reports.

Exceeding these limits will result in a `429 Too Many Requests` error. 

---

## Endpoints

### **OAuth Endpoints**

#### 1. `/public-api/OAuth/token` (POST)

**Description**:  
Authenticates the client and returns an access token.

**Request Parameters**:
- `client_id` (string): Your unique client identifier.
- `client_secret` (string): Your client secret.
- `grant_type` (string): Must be `client_credentials`.

**Response**:
- **Success (200)**:  
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```
- **Error (400)**: Invalid credentials.

#### 2. `/public-api/OAuth/token/refresh` (POST)

**Description**:  
Refreshes an expired token.

**Request Parameters**:
- `refresh_token` (string): The refresh token from the original request.

**Response**:
- **Success (200)**: New access token.
- **Error (400)**: Invalid refresh token.

---

### **Bulk Report Endpoints** (`/bulkreport`)

#### 1. `/bulkreport/meters/bulk-retrieve-readings` (POST)

**Description**:  
Retrieves bulk meter readings for a specific division and date.

**Request Parameters**:
- `logical_device_names` (array): List of logical device names.
- `division_id` (string): Division identifier (e.g., `DD1`, `DD2`).
- `date` (string): Date in `YYYY-MM-DD` format. Must be the first of the month.

**Response**:
- **Success (200)**:
  ```json
  {
    "result": [
      { "logical_device_name": "device1", "reading_status": "success", "data": {...} },
      { "logical_device_name": "device2", "reading_status": "error", "message": "Device not found" }
    ]
  }
  ```
- **Error (400)**: Invalid parameters.
- **Error (500)**: Server error.

---

### **Ordinary Report Endpoints** (`/ordinaryreport`)

#### 1. `/ordinaryreport/meters/retrieve-readings` (POST)

**Description**:  
Retrieves meter readings for a specific device within a date range.

**Request Parameters**:
- `logical_device_name` (string): Logical device name.
- `division_id` (string): Division identifier (e.g., `DD1`, `DD2`).
- `start_date` (string): Start date (`YYYY-MM-DD`).
- `end_date` (string): End date (`YYYY-MM-DD`).

**Response**:
- **Success (200)**:
  ```json
  {
    "result": [
      { "date": "2024-10-01", "reading": 123.45 },
      { "date": "2024-10-02", "reading": 127.56 }
    ]
  }
  ```
- **Error (400)**: Invalid parameters.
- **Error (500)**: Server error.

---

## Error Codes

- `400 Bad Request`: Invalid or missing parameters.
- `401 Unauthorized`: Missing or invalid authentication token.
- `403 Forbidden`: Insufficient permissions to access the resource.
- `429 Too Many Requests`: Rate limit exceeded.
- `500 Internal Server Error`: Unexpected server error.

---

## Token and Permissions

Each request requires a valid OAuth2 token. Permissions are checked per client, and requests without proper authorization will return a `401 Unauthorized` error.
