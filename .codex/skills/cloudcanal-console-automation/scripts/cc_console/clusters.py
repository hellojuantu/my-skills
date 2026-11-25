from cc_console.utils import parse_int, print_json, prompt_line


QUERY_DEFAULT_CLUSTER_PATH = "/cloudcanal/console/api/v1/inner/cluster/querydefaultcluster"
LIST_CLUSTERS_PATH = "/cloudcanal/console/api/v1/inner/cluster/listbycondition"


def cluster_label(cluster):
    parts = [str(cluster.get("id"))]
    if cluster.get("clusterName"):
        parts.append(str(cluster.get("clusterName")))
    if cluster.get("region"):
        parts.append(str(cluster.get("region")))
    if cluster.get("workerCount") is not None:
        parts.append("workers=" + str(cluster.get("workerCount")))
    return " / ".join(parts)


def query_default_cluster(client):
    response = client.post_json(QUERY_DEFAULT_CLUSTER_PATH, {})
    data = client.ensure_success(response, "query default cluster")
    if data and data.get("id"):
        return data
    return None


def list_clusters(client, name_like=None):
    payload = {}
    if name_like:
        payload["clusterNameLike"] = name_like
    response = client.post_json(LIST_CLUSTERS_PATH, payload)
    data = client.ensure_success(response, "list clusters")
    return data or []


def resolve_cluster_id(args, client):
    value = getattr(args, "cluster_id", None)
    if value:
        return value

    import os
    env_value = os.environ.get("CC_CLUSTER_ID", "").strip()
    if env_value:
        return parse_int(env_value, "CC_CLUSTER_ID")

    name_like = getattr(args, "cluster_name_like", None)
    if not name_like:
        default_cluster = query_default_cluster(client)
        if default_cluster:
            print("Use default cluster, " + cluster_label(default_cluster))
            return parse_int(default_cluster.get("id"), "default cluster id")

    clusters = list_clusters(client, name_like)
    if len(clusters) == 1:
        print("Use only matched cluster, " + cluster_label(clusters[0]))
        return parse_int(clusters[0].get("id"), "cluster id")

    if getattr(args, "non_interactive", False):
        raise ValueError("--cluster-id is required; default cluster is empty or ambiguous")
    if clusters:
        print("\nAvailable clusters:")
        for cluster in clusters:
            print("  " + cluster_label(cluster))
    return parse_int(prompt_line("Cluster id", required=True), "cluster id")


def list_cluster_cmd(args, client):
    if args.default:
        print_json(query_default_cluster(client) or {})
        return 0
    print_json(list_clusters(client, args.cluster_name_like))
    return 0
