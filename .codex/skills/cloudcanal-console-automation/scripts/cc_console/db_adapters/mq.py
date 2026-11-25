import json
import time

from cc_console.datasource import choose_test_host, default_port

from .base import AdapterCapabilityError, parse_host_port
from .object_common import NamespacedObjectAdapter, json_bytes


class KafkaFamilyAdapter(NamespacedObjectAdapter):
    name = "kafka-family"
    data_source_types = ("Kafka", "AmazonMSK", "AutoMQ")
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("kafka",)
    install_commands = ("python3 -m pip install kafka-python",)
    default_profile = "kafka-core"
    data_model = "mq-topic"
    object_label = "topic"

    def _bootstrap(self, ds, **kwargs):
        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("Kafka"))
        return str(host) + ":" + str(port)

    def _create_object(self, ds, password, table, **kwargs):
        self.require_dependencies()
        from kafka.admin import KafkaAdminClient, NewTopic

        admin = KafkaAdminClient(bootstrap_servers=self._bootstrap(ds, **kwargs), client_id="cc-autotest-admin")
        try:
            if table not in admin.list_topics():
                admin.create_topics([NewTopic(name=table, num_partitions=1, replication_factor=1)], validate_only=False)
        finally:
            admin.close()

    def _delete_object(self, ds, password, table, **kwargs):
        self.require_dependencies()
        from kafka.admin import KafkaAdminClient

        admin = KafkaAdminClient(bootstrap_servers=self._bootstrap(ds, **kwargs), client_id="cc-autotest-admin")
        try:
            if table in admin.list_topics():
                admin.delete_topics([table])
        finally:
            admin.close()

    def _object_exists(self, ds, password, table, **kwargs):
        self.require_dependencies()
        from kafka.admin import KafkaAdminClient

        admin = KafkaAdminClient(bootstrap_servers=self._bootstrap(ds, **kwargs), client_id="cc-autotest-admin")
        try:
            return table in admin.list_topics()
        finally:
            admin.close()

    def _write_records(self, ds, password, table, records, **kwargs):
        self.require_dependencies()
        from kafka import KafkaProducer

        producer = KafkaProducer(bootstrap_servers=self._bootstrap(ds, **kwargs))
        for record in records:
            producer.send(table, key=str(record["id"]).encode("utf-8"), value=json_bytes(record))
        producer.flush(timeout=30)
        producer.close()
        return len(records)

    def _offsets(self, ds, table, **kwargs):
        self.require_dependencies()
        from kafka import KafkaConsumer, TopicPartition

        consumer = KafkaConsumer(bootstrap_servers=self._bootstrap(ds, **kwargs), enable_auto_commit=False, consumer_timeout_ms=1000)
        partitions = consumer.partitions_for_topic(table) or set()
        topic_partitions = [TopicPartition(table, part) for part in partitions]
        if not topic_partitions:
            consumer.close()
            return [], {}, {}
        beginning = consumer.beginning_offsets(topic_partitions)
        end = consumer.end_offsets(topic_partitions)
        consumer.close()
        return topic_partitions, beginning, end

    def _count_records(self, ds, password, table, **kwargs):
        topic_partitions, beginning, end = self._offsets(ds, table, **kwargs)
        return sum(int(end.get(tp, 0)) - int(beginning.get(tp, 0)) for tp in topic_partitions)

    def _read_records(self, ds, password, table, **kwargs):
        self.require_dependencies()
        from kafka import KafkaConsumer

        consumer = KafkaConsumer(
            table,
            bootstrap_servers=self._bootstrap(ds, **kwargs),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=2000,
            group_id="cc-autotest-snapshot-" + str(int(time.time() * 1000)),
        )
        values = []
        try:
            for message in consumer:
                try:
                    values.append(json.loads(message.value.decode("utf-8")))
                except Exception:
                    values.append({"value": message.value.decode("utf-8", errors="replace")})
            return values
        finally:
            consumer.close()


class RocketMqFamilyAdapter(NamespacedObjectAdapter):
    name = "rocketmq-family"
    data_source_types = ("RocketMQ",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("rocketmq",)
    install_commands = ("python3 -m pip install rocketmq-client-python",)
    default_profile = "rocketmq-core"
    data_model = "mq-topic"
    object_label = "rmq"
    can_compare = False

    def _namesrv(self, ds, **kwargs):
        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("RocketMQ"))
        return str(host) + ":" + str(port)

    def _create_object(self, ds, password, table, **kwargs):
        return True

    def _delete_object(self, ds, password, table, **kwargs):
        return True

    def _object_exists(self, ds, password, table, **kwargs):
        return True

    def _write_records(self, ds, password, table, records, **kwargs):
        self.require_dependencies()
        from rocketmq.client import Message, Producer

        producer = Producer("cc_autotest_producer")
        producer.set_namesrv_addr(self._namesrv(ds, **kwargs))
        producer.start()
        try:
            for record in records:
                msg = Message(table)
                msg.set_keys(str(record["id"]))
                msg.set_body(json_bytes(record))
                producer.send_sync(msg)
            return len(records)
        finally:
            producer.shutdown()

    def _count_records(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError("RocketMQ Python client cannot safely count topic messages; use CloudCanal check child or a RocketMQ admin trace for this pair")

    def _read_records(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError("RocketMQ Python client cannot safely snapshot topic messages")


class RabbitMqFamilyAdapter(NamespacedObjectAdapter):
    name = "rabbitmq-family"
    data_source_types = ("RabbitMQ",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("pika",)
    install_commands = ("python3 -m pip install pika",)
    default_profile = "rabbitmq-core"
    data_model = "mq-queue"
    object_label = "queue"

    def _connection(self, ds, password, **kwargs):
        self.require_dependencies()
        import pika

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("RabbitMQ"))
        credentials = None
        user = kwargs.get("user") or ds.get("accountName")
        if user:
            credentials = pika.PlainCredentials(user, password or "")
        params = pika.ConnectionParameters(host=host, port=port, virtual_host=ds.get("dbName") or "/", credentials=credentials)
        return pika.BlockingConnection(params)

    def _create_object(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            conn.channel().queue_declare(queue=table, durable=True)
        finally:
            conn.close()

    def _delete_object(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            conn.channel().queue_delete(queue=table)
        except Exception:
            pass
        finally:
            conn.close()

    def _object_exists(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            conn.channel().queue_declare(queue=table, passive=True)
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def _write_records(self, ds, password, table, records, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            ch = conn.channel()
            ch.queue_declare(queue=table, durable=True)
            for record in records:
                ch.basic_publish(exchange="", routing_key=table, body=json_bytes(record))
            return len(records)
        finally:
            conn.close()

    def _count_records(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            method = conn.channel().queue_declare(queue=table, passive=True)
            return int(method.method.message_count)
        finally:
            conn.close()

    def _read_records(self, ds, password, table, **kwargs):
        return [{"message_count": self._count_records(ds, password, table, **kwargs)}]


class PulsarFamilyAdapter(NamespacedObjectAdapter):
    name = "pulsar-family"
    data_source_types = ("Pulsar",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("pulsar",)
    install_commands = ("python3 -m pip install pulsar-client",)
    default_profile = "pulsar-core"
    data_model = "mq-topic"
    object_label = "pulsar"

    def _service_url(self, ds, **kwargs):
        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        if str(host_value).startswith(("pulsar://", "http://", "https://")):
            return host_value
        host, port = parse_host_port(host_value, default_port("Pulsar"))
        return "pulsar://" + str(host) + ":" + str(port)

    def _client(self, ds, password, **kwargs):
        self.require_dependencies()
        import pulsar

        return pulsar.Client(self._service_url(ds, **kwargs))

    def _create_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            producer = client.create_producer(table)
            producer.close()
        finally:
            client.close()

    def _delete_object(self, ds, password, table, **kwargs):
        return True

    def _object_exists(self, ds, password, table, **kwargs):
        return True

    def _write_records(self, ds, password, table, records, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            producer = client.create_producer(table)
            for record in records:
                producer.send(json_bytes(record), partition_key=str(record["id"]))
            producer.close()
            return len(records)
        finally:
            client.close()

    def _count_records(self, ds, password, table, **kwargs):
        return len(self._read_records(ds, password, table, **kwargs))

    def _read_records(self, ds, password, table, **kwargs):
        self.require_dependencies()
        import pulsar

        client = self._client(ds, password, **kwargs)
        subscription = "cc-autotest-snapshot-" + str(int(time.time() * 1000))
        values = []
        try:
            consumer = client.subscribe(table, subscription_name=subscription, initial_position=pulsar.InitialPosition.Earliest)
            while True:
                try:
                    msg = consumer.receive(timeout_millis=500)
                except Exception:
                    break
                try:
                    values.append(json.loads(msg.data().decode("utf-8")))
                except Exception:
                    values.append({"value": msg.data().decode("utf-8", errors="replace")})
                consumer.acknowledge(msg)
            consumer.close()
            return values
        finally:
            client.close()
