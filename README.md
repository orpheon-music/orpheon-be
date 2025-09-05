# Orpheon BE

TBD

## Getting Started

### Prerequisites

- Python 3.13 or higher
- `uv` package installer

#### 1. Set Up a Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies. Assuming you are in the project directory:

```bash
uv venv
```

#### 2. Install Dependencies

Install all the required Python packages

```bash
uv sync
```

#### 3. Generate gRPC Code from Proto File
If you have made changes to the `echo.proto` file or are setting up the project for the first time, you need to generate the gRPC Python files.

```bash
chmod +x gen_echo_proto.sh
./gen_echo_proto.sh
```

#### 4. Run the API Server

Start the application using Uvicorn.

```bash
chmod +x run.sh
./run.sh
```

The server is now running and accessible at `http://127.0.0.1:8000`. The `--reload` flag will automatically restart the server when you make code changes.
