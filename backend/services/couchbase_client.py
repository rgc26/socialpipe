from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from datetime import timedelta
import os
from typing import List, Optional, Dict, Any

class CouchbaseClient:
    def __init__(self):
        self.conn_str = os.getenv("COUCHBASE_CONNECTION_STRING")
        self.username = os.getenv("COUCHBASE_USERNAME")
        self.password = os.getenv("COUCHBASE_PASSWORD")
        self.bucket_name = os.getenv("COUCHBASE_BUCKET", "socialpipe")
        self.config_profile = os.getenv("COUCHBASE_CONFIG_PROFILE", "wan_development")
        
        self.cluster = None
        self.bucket = None
        self.collection = None
        
        # In-memory store for fallback
        self._memory_store: Dict[str, Any] = {}
        
        if self.conn_str and self.username and self.password:
            self.connect()
        else:
            print("Couchbase credentials missing. Falling back to in-memory store.")

    def connect(self):
        """
        Establish connection to Couchbase Capella.
        """
        try:
            print(f"Connecting to Couchbase at: {self.conn_str}...")
            auth = PasswordAuthenticator(self.username, self.password)
            
            from couchbase.options import ClusterOptions, ClusterTimeoutOptions
            timeout_opts = ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10), query_timeout=timedelta(seconds=20))
            
            cluster_opts = ClusterOptions(auth, timeout_options=timeout_opts)
            if self.config_profile:
                try:
                    cluster_opts.apply_profile(self.config_profile)
                except Exception as e:
                    print(f"Warning: failed to apply Couchbase config profile '{self.config_profile}': {e}")

            self.cluster = Cluster(self.conn_str, cluster_opts)
            self.cluster.wait_until_ready(timedelta(seconds=10))
            
            self.bucket = self.cluster.bucket(self.bucket_name)
            self.collection = self.bucket.default_collection()
            print(f"Successfully connected to Couchbase bucket: '{self.bucket_name}'")
        except Exception as e:
            print(f"CRITICAL: Couchbase connection failed. Using in-memory store. Error: {str(e)}")
            self.cluster = None
            self.bucket = None
            self.collection = None

    def save_lead(self, lead: Dict[str, Any]) -> bool:
        doc_id = lead.get("id")
        if not doc_id:
            return False

        if "doc_type" not in lead:
            lead["doc_type"] = "lead"

        if self.collection:
            try:
                self.collection.upsert(doc_id, lead)
                return True
            except Exception as e:
                print(f"Error saving to Couchbase: {e}")
        
        self._memory_store[doc_id] = lead
        return True

    def get_all_leads(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.cluster:
            try:
                from couchbase.options import QueryOptions

                query = f"SELECT l.* FROM `{self.bucket_name}` AS l WHERE l.doc_type = $doc_type"
                params: Dict[str, Any] = {"doc_type": "lead"}
                if status:
                    query += " AND l.status = $status"
                    params["status"] = status

                result = self.cluster.query(query, QueryOptions(named_parameters=params))
                return [row for row in result]
            except Exception as e:
                print(f"Error fetching from Couchbase: {e}")

        leads = list(self._memory_store.values())
        if status:
            return [l for l in leads if l.get("status") == status]
        return leads

    def get_lead_by_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        if self.collection:
            try:
                return self.collection.get(lead_id).content_as[dict]
            except Exception:
                pass
        return self._memory_store.get(lead_id)

    def update_lead_status(self, lead_id: str, status: str) -> bool:
        if self.collection:
            try:
                import couchbase.subdocument as SD
                self.collection.mutate_in(lead_id, [SD.upsert("status", status)])
                return True
            except Exception:
                pass
        
        if lead_id in self._memory_store:
            self._memory_store[lead_id]["status"] = status
            return True
        return False

    def get_analytics(self) -> Dict[str, Any]:
        if self.cluster:
            try:
                from couchbase.options import QueryOptions

                status_query = f"SELECT l.status AS status, COUNT(*) AS count FROM `{self.bucket_name}` AS l WHERE l.doc_type = $doc_type GROUP BY l.status"
                platform_query = f"SELECT l.platform AS platform, COUNT(*) AS count FROM `{self.bucket_name}` AS l WHERE l.doc_type = $doc_type GROUP BY l.platform"
                opts = QueryOptions(named_parameters={"doc_type": "lead"})
                return {
                    "by_status": {row["status"]: row["count"] for row in self.cluster.query(status_query, opts)},
                    "by_platform": {row["platform"]: row["count"] for row in self.cluster.query(platform_query, opts)}
                }
            except Exception as e:
                print(f"Error fetching analytics: {e}")
        
        leads = list(self._memory_store.values())
        by_status = {}
        by_platform = {}
        for l in leads:
            s = l.get("status", "unknown")
            p = l.get("platform", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            by_platform[p] = by_platform.get(p, 0) + 1
        return {"by_status": by_status, "by_platform": by_platform}

couchbase_client = CouchbaseClient()
