# Create the output directory if it doesn't exist
mkdir -p gen

# Generate Python files from proto
uv run python -m grpc_tools.protoc \
    -I proto \
    --python_out=gen \
    --grpc_python_out=gen \
    $(find proto -name "*.proto")

# Create __init__.py files if they don't exist
touch gen/__init__.py

echo "gRPC Python files generated successfully!"
echo "Generated files:"
for proto_file in $(find proto -name "*.proto"); do
    base_name=$(basename "$proto_file" .proto)
    echo "  - gen/${base_name}_pb2.py"
    echo "  - gen/${base_name}_pb2_grpc.py"
done
