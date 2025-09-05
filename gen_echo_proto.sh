# Create the output directory if it doesn't exist
mkdir -p app/infra/external_services/proto_gen

# Generate Python files from proto
uv run python -m grpc_tools.protoc \
    -I proto \
    --python_out=app/infra/external_services/proto_gen \
    --grpc_python_out=app/infra/external_services/proto_gen \
    $(find proto -name "*.proto")

# Create __init__.py files if they don't exist
touch app/infra/external_services/proto_gen/__init__.py

echo "gRPC Python files generated successfully!"
echo "Generated files:"
for proto_file in $(find proto -name "*.proto"); do
    base_name=$(basename "$proto_file" .proto)
    echo "  - app/infra/external_services/proto_gen/${base_name}_pb2.py"
    echo "  - app/infra/external_services/proto_gen/${base_name}_pb2_grpc.py"
done
