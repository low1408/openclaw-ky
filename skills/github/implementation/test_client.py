import grpc
import github_rpc_pb2
import github_rpc_pb2_grpc

def run():
    print("Connecting to gRPC server at localhost:50051...")
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = github_rpc_pb2_grpc.GitHubRpcStub(channel)
        
        print("\n-------------- Testing ListPullRequests --------------")
        try:
            request = github_rpc_pb2.ListPullRequestsRequest(
                repo=github_rpc_pb2.RepoRef(owner="openclaw", name="openclaw"),
                state="open",
                limit=3
            )
            response = stub.ListPullRequests(request)
            for pr in response.items:
                print(f"PR #{pr.number}: {pr.title} ({pr.state}) by {pr.author_login}")
            print("Successfully received PR list!")
        except Exception as e:
            print(f"gRPC call failed: {e}")

if __name__ == '__main__':
    run()
