### Saberis2Jobber: Docker Deployment Checklist

This plan outlines the necessary steps to take your Flask application from its current state to a live, containerized prototype using Docker on a PaaS like Render.

### Phase 1: Code & Configuration Hardening

These changes prepare your app to be packaged in a Docker container and run in a production environment.

#### ✅ 1\. Add a Production Web Server

Even inside a Docker container, Flask's development server should not be used. Gunicorn is still required to handle web requests efficiently.

-   Action: Ensure `gunicorn` is in your `requirements.txt` file.

    ```
    # requirements.txt
    Flask==3.0.3
    requests==2.31.0
    python-dotenv==1.0.1
    google-api-python-client==2.125.0
    google-auth-httplib2==0.2.0
    google-auth-oauthlib==1.2.0
    gspread==6.0.0
    gunicorn==22.0.0  # <-- This is still required

    ```

#### ✅ 2\. Create a `Dockerfile`

This is the new core of your deployment. The `Dockerfile` is a recipe that tells Docker how to build a self-contained image of your application. It replaces the need for a `Procfile`.

-   Action: Create a new file named `Dockerfile` (no file extension) in the root directory of your project.

-   Content:

    ```
    # Dockerfile

    # --- Stage 1: Build Stage ---
    # Use an official Python runtime as a parent image
    FROM python:3.11-slim as builder

    # Set the working directory in the container
    WORKDIR /app

    # Copy the requirements file into the container at /app
    COPY requirements.txt .

    # Install any needed packages specified in requirements.txt
    # --no-cache-dir ensures we don't store the download cache, keeping the image small
    RUN pip install --no-cache-dir -r requirements.txt

    # --- Stage 2: Final Stage ---
    # Use a smaller, non-root user base image for security
    FROM python:3.11-slim

    WORKDIR /app

    # Copy the installed packages from the builder stage
    COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
    COPY --from=builder /usr/local/bin /usr/local/bin

    # Copy the application source code into the container
    COPY src/ .

    # Tell Docker that the container will listen on this port
    EXPOSE 8080

    # Define the command to run your app using Gunicorn
    # Binds to all network interfaces on the specified port
    CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]

    ```

#### ✅ 3\. Critical: Refactor Token Storage for a Stateless Environment

This remains the most important code change. The Docker container has an ephemeral filesystem, just like a PaaS without Docker. Files saved inside the container will be lost on restart.

-   Action: Modify `src/token_storage.py` and `src/saberis_token_storage.py` to read tokens from environment variables (`JOBBER_TOKEN_JSON`, `SABERIS_TOKEN_JSON`) instead of local `.json` files.

-   Updated Code for `src/token_storage.py` (Jobber):

    ```
    # src/token_storage.py
    import os
    import json
    from typing import Dict, Any

    def load_token() -> Dict[str, Any] | None:
        """
        Loads the Jobber token from the JOBBER_TOKEN_JSON environment variable.
        """
        token_str = os.getenv("JOBBER_TOKEN_JSON")
        if not token_str:
            print("Warning: JOBBER_TOKEN_JSON environment variable not found.")
            return None
        try:
            return json.loads(token_str)
        except json.JSONDecodeError:
            print("Error: Could not decode JOBBER_TOKEN_JSON. Ensure it is valid JSON.")
            return None

    def save_token(token: Dict[str, Any]) -> None:
        """
        In a stateless production environment, this function's main purpose is to
        display the token so it can be manually updated in the environment variables.
        """
        print("--- NEW JOBBER TOKEN ---")
        print("To update, copy the following line into your .env file or hosting provider's environment variables:")
        print(f"JOBBER_TOKEN_JSON='{json.dumps(token)}'")
        print("------------------------")

    ```

-   Updated Code for `src/saberis_token_storage.py` (Saberis):

    ```
    # src/saberis_token_storage.py
    import os
    import json
    from typing import Dict, Any

    def load_token() -> Dict[str, Any] | None:
        """
        Loads the Saberis token from the SABERIS_TOKEN_JSON environment variable.
        """
        token_str = os.getenv("SABERIS_TOKEN_JSON")
        if not token_str:
            print("Warning: SABERIS_TOKEN_JSON environment variable not found.")
            return None
        try:
            return json.loads(token_str)
        except json.JSONDecodeError:
            print("Error: Could not decode SABERIS_TOKEN_JSON. Ensure it is valid JSON.")
            return None

    def save_token(token: Dict[str, Any]) -> None:
        """
        In a stateless production environment, this function's main purpose is to
        display the token so it can be manually updated in the environment variables.
        """
        print("--- NEW SABERIS TOKEN ---")
        print("To update, copy the following line into your .env file or hosting provider's environment variables:")
        print(f"SABERIS_TOKEN_JSON='{json.dumps(token)}'")
        print("-------------------------")

    ```

#### ✅ 4\. Update `.gitignore`

In addition to ignoring `.json` token files, you should also ignore Docker-related artifacts.

-   Action: Add `*.json` and `.dockerignore` to your `.gitignore` file. You should also create a `.dockerignore` file to prevent copying unnecessary files into your container.

-   New file: `.dockerignore` (in the root directory)

    ```
    # .dockerignore
    __pycache__/
    *.pyc
    .env
    .venv
    .git
    .gitignore
    .vscode/

    ```

### Phase 2: Deployment on a PaaS (e.g., Render) with Docker

1.  Push Code to GitHub: Make sure all your changes from Phase 1, including the new `Dockerfile`, are committed and pushed to your GitHub repository.

2.  Create a Render Account & New Web Service:

    -   Sign up for Render.

    -   Click "New" -> "Web Service" and connect your GitHub account.

    -   Select your `Saberis2Jobber` repository.

3.  Configure the Render Service:

    -   Name: Give your app a name (e.g., `saberis-jobber-tool`).

    -   Environment: Select `Docker`. This is the key change. Render will automatically detect and use your `Dockerfile`.

    -   Build & Deploy: Render will handle the rest. You don't need to specify a build or start command.

4.  Set Environment Variables:

    -   Go to the "Environment" tab for your new service.

    -   This step is identical to the previous plan. You must add all your secrets (`JOBBER_APP_ID`, etc.) here.

    -   Most importantly, you must run the app locally one last time to get fresh tokens, copy their JSON content, and paste them into the `JOBBER_TOKEN_JSON` and `SABERIS_TOKEN_JSON` environment variables in Render.

5.  Deploy:

    -   Click "Create Web Service". Render will now pull your code, build the Docker image according to your `Dockerfile`, and start the container.

    -   Monitor the logs to ensure the container builds and the Gunicorn server starts successfully.