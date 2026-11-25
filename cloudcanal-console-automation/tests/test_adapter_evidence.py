from collections import namedtuple
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cc_console.db_adapters import adapter_for_type
from cc_console.db_adapters.base import AdapterCapabilityError


class AdapterEvidenceTest(unittest.TestCase):
    def test_mq_topic_cleanup_and_unreadable_snapshots_fail_without_a_driver(self):
        for engine in ("Pulsar", "RocketMQ"):
            with self.subTest(engine=engine):
                adapter = adapter_for_type(engine)
                caps = adapter.capabilities()
                self.assertFalse(caps["cleanup"])
                self.assertFalse(caps["compare"])
                self.assertFalse(caps["prepareTarget"])
                with self.assertRaises(AdapterCapabilityError):
                    adapter.cleanup_dataset({}, "", "cc_auto_src", False, tables=["cc_auto_topic"])
                for mode in ("count", "digest"):
                    with self.assertRaises(AdapterCapabilityError):
                        adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_topic", mode, False)

    def test_elasticsearch_digest_requires_every_hit(self):
        adapter = adapter_for_type("ElasticSearch")
        client = Mock()
        hits = [{"_source": {"id": "1"}}]
        with patch.object(adapter, "_client", return_value=client):
            for total, page, errors in (
                ({"relation": "eq", "value": 10001}, hits * 10000, {}),
                ({"relation": "gte", "value": 1}, hits, {}),
                ({"relation": "eq", "value": 1}, hits, {"_shards": {"failed": 1}}),
                ({"relation": "eq", "value": 1}, hits, {"timed_out": True}),
            ):
                client.search.return_value = {"hits": {"total": total, "hits": page}, **errors}
                with self.assertRaises(AdapterCapabilityError):
                    adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_idx", "digest", False)
            client.search.return_value = {"hits": {"total": {"relation": "eq", "value": 1}, "hits": hits}}
            result = adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_idx", "digest", False)
            self.assertEqual(1, result["rows"])
            self.assertTrue(result["digest"])
            self.assertTrue(client.search.call_args.kwargs["track_total_hits"])

    def test_redis_exists_scans_until_a_key_matches(self):
        adapter = adapter_for_type("Redis")
        client = Mock()
        client.scan_iter.side_effect = [iter([b"cc_auto_keys:42"]), iter([])]
        with patch.object(adapter, "_client", return_value=client), patch.object(adapter, "_count_records", return_value=1):
            for exists in (True, False):
                result = adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_keys", "count", False)
                self.assertEqual(exists, result["exists"])
        client.scan_iter.assert_called_with(match=b"cc_auto_keys:*", count=500)

    def test_rabbitmq_reports_delete_failure_and_requires_count_mode(self):
        adapter = adapter_for_type("RabbitMQ")
        connection = Mock()
        connection.channel.return_value.queue_delete.side_effect = PermissionError("no queue delete")
        with patch.object(adapter, "_connection", return_value=connection):
            with self.assertRaises(PermissionError):
                adapter.cleanup_dataset({}, "", "cc_auto_src", False, tables=["cc_auto_queue"])
            with self.assertRaises(AdapterCapabilityError):
                adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_queue", "digest", False)

    def test_kafka_consumer_timeout_cannot_complete_a_partial_digest(self):
        adapter = adapter_for_type("Kafka")
        partition = namedtuple("TopicPartition", "topic partition")("cc_auto_topic", 0)
        consumer = MagicMock()
        consumer.assignment.return_value = {partition}
        consumer.partitions_for_topic.return_value = {0}
        consumer.end_offsets.return_value = {partition: 1}
        consumer.position.return_value = 0
        kafka = Mock()
        kafka.KafkaConsumer.return_value = consumer
        with patch.dict(sys.modules, {"kafka": kafka}), patch.object(adapter, "_bootstrap", return_value="fixture"), patch.object(adapter, "require_dependencies"):
            with self.assertRaisesRegex(AdapterCapabilityError, "before the end"):
                adapter.table_snapshot({}, "", "cc_auto_src", "cc_auto_topic", "digest", False)
        consumer.close.assert_called_once()
