"""
ArchitectIQ - Predefined System Architecture Presets
Provides industry-standard architectures ready for simulation, optimization, and chaos testing.
"""

from __future__ import annotations

from typing import Any, Dict, List

SYSTEM_PRESETS: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "id": "ecommerce",
        "name": "E-Commerce Microservices Platform",
        "description": "High-volume distributed storefront with ingress load balancer, microservice API gateway, catalog cache, order queues, and async billing workers.",
        "architecture": {
            "architecture_id": "arch-ecommerce-01",
            "components": [
                {
                    "id": "lb-1",
                    "type": "load_balancer",
                    "name": "Public Ingress LB",
                    "capacity_rps": 5000.0,
                    "replicas": 2,
                    "base_latency_ms": 2.0,
                    "cost_per_month_usd": 50.0,
                },
                {
                    "id": "api-gateway",
                    "type": "api_server",
                    "name": "Storefront Gateway",
                    "capacity_rps": 1200.0,
                    "replicas": 3,
                    "base_latency_ms": 12.0,
                    "cost_per_month_usd": 120.0,
                },
                {
                    "id": "cache-redis",
                    "type": "cache",
                    "name": "Product Catalog Cache",
                    "capacity_rps": 8000.0,
                    "replicas": 1,
                    "base_latency_ms": 1.5,
                    "cache_hit_ratio": 0.85,
                    "cost_per_month_usd": 60.0,
                },
                {
                    "id": "db-primary",
                    "type": "database",
                    "name": "PostgreSQL Primary",
                    "capacity_rps": 800.0,
                    "replicas": 1,
                    "base_latency_ms": 25.0,
                    "cost_per_month_usd": 140.0,
                },
                {
                    "id": "queue-orders",
                    "type": "message_broker",
                    "name": "RabbitMQ Orders Queue",
                    "capacity_rps": 4000.0,
                    "replicas": 1,
                    "base_latency_ms": 4.0,
                    "cost_per_month_usd": 35.0,
                },
                {
                    "id": "worker-billing",
                    "type": "api_server",
                    "name": "Billing Async Consumer",
                    "capacity_rps": 600.0,
                    "replicas": 2,
                    "base_latency_ms": 30.0,
                    "cost_per_month_usd": 80.0,
                },
            ],
            "connections": [
                {
                    "source": "lb-1",
                    "target": "api-gateway",
                    "protocol": "http",
                    "latency_overhead_ms": 1.0,
                    "path_type": "both",
                },
                {
                    "source": "api-gateway",
                    "target": "cache-redis",
                    "protocol": "redis",
                    "latency_overhead_ms": 1.2,
                    "path_type": "read",
                },
                {
                    "source": "api-gateway",
                    "target": "db-primary",
                    "protocol": "sql",
                    "latency_overhead_ms": 2.0,
                    "path_type": "both",
                },
                {
                    "source": "api-gateway",
                    "target": "queue-orders",
                    "protocol": "amqp",
                    "latency_overhead_ms": 1.5,
                    "path_type": "write",
                },
                {
                    "source": "queue-orders",
                    "target": "worker-billing",
                    "protocol": "amqp",
                    "latency_overhead_ms": 1.5,
                    "path_type": "write",
                },
            ],
            "workload": {
                "requests_per_second": 1500.0,
                "read_ratio": 0.85,
                "write_ratio": 0.15,
                "duration_seconds": 10,
                "burst_multiplier": 2.0,
            },
            "constraints": {
                "max_p95_latency_ms": 180.0,
                "min_throughput_rps": 1400.0,
                "max_cost_per_hour": 1.50,
            },
        },
    },
    "payments": {
        "id": "payments",
        "name": "FinTech High-Assurance Payments Gateway",
        "description": "PCI-DSS compliant payment processing architecture with dedicated WAF, cryptographic authorization workers, and ACID-compliant Aurora database.",
        "architecture": {
            "architecture_id": "arch-payments-02",
            "components": [
                {
                    "id": "waf-gateway",
                    "type": "load_balancer",
                    "name": "Cloudflare / WAF Edge Gateway",
                    "capacity_rps": 4000.0,
                    "replicas": 2,
                    "base_latency_ms": 3.0,
                    "cost_per_month_usd": 60.0,
                },
                {
                    "id": "payment-api",
                    "type": "api_server",
                    "name": "Card Authorization Service",
                    "capacity_rps": 1000.0,
                    "replicas": 2,
                    "base_latency_ms": 18.0,
                    "cost_per_month_usd": 100.0,
                },
                {
                    "id": "ledger-db",
                    "type": "database",
                    "name": "Aurora PostgreSQL Ledger",
                    "capacity_rps": 600.0,
                    "replicas": 1,
                    "base_latency_ms": 35.0,
                    "cost_per_month_usd": 220.0,
                },
                {
                    "id": "fraud-detector",
                    "type": "api_server",
                    "name": "Fraud Detection ML Sidecar",
                    "capacity_rps": 1200.0,
                    "replicas": 2,
                    "base_latency_ms": 14.0,
                    "cost_per_month_usd": 90.0,
                },
            ],
            "connections": [
                {
                    "source": "waf-gateway",
                    "target": "payment-api",
                    "protocol": "http",
                    "latency_overhead_ms": 1.5,
                    "path_type": "both",
                },
                {
                    "source": "payment-api",
                    "target": "fraud-detector",
                    "protocol": "grpc",
                    "latency_overhead_ms": 0.8,
                    "path_type": "both",
                },
                {
                    "source": "payment-api",
                    "target": "ledger-db",
                    "protocol": "sql",
                    "latency_overhead_ms": 2.5,
                    "path_type": "both",
                },
            ],
            "workload": {
                "requests_per_second": 800.0,
                "read_ratio": 0.30,
                "write_ratio": 0.70,
                "duration_seconds": 10,
                "burst_multiplier": 1.5,
            },
            "constraints": {
                "max_p95_latency_ms": 120.0,
                "min_throughput_rps": 750.0,
                "max_cost_per_hour": 2.00,
            },
        },
    },
    "cdn_streaming": {
        "id": "cdn_streaming",
        "name": "Content Delivery & Video Streaming Platform",
        "description": "High-bandwidth edge distribution network with Anycast CDN cache, stream segment transcoders, and persistent object storage origin.",
        "architecture": {
            "architecture_id": "arch-cdn-03",
            "components": [
                {
                    "id": "edge-cdn",
                    "type": "cache",
                    "name": "Anycast Edge CDN",
                    "capacity_rps": 15000.0,
                    "replicas": 4,
                    "base_latency_ms": 1.0,
                    "cache_hit_ratio": 0.92,
                    "cost_per_month_usd": 150.0,
                },
                {
                    "id": "stream-router",
                    "type": "api_server",
                    "name": "HLS Manifest Router",
                    "capacity_rps": 3500.0,
                    "replicas": 2,
                    "base_latency_ms": 6.0,
                    "cost_per_month_usd": 85.0,
                },
                {
                    "id": "metadata-cache",
                    "type": "cache",
                    "name": "Redis Video Catalog Cache",
                    "capacity_rps": 10000.0,
                    "replicas": 1,
                    "base_latency_ms": 1.5,
                    "cache_hit_ratio": 0.90,
                    "cost_per_month_usd": 55.0,
                },
                {
                    "id": "object-origin",
                    "type": "database",
                    "name": "S3 Video Segment Storage",
                    "capacity_rps": 2000.0,
                    "replicas": 1,
                    "base_latency_ms": 40.0,
                    "cost_per_month_usd": 180.0,
                },
            ],
            "connections": [
                {
                    "source": "edge-cdn",
                    "target": "stream-router",
                    "protocol": "http",
                    "latency_overhead_ms": 2.0,
                    "path_type": "both",
                },
                {
                    "source": "stream-router",
                    "target": "metadata-cache",
                    "protocol": "redis",
                    "latency_overhead_ms": 1.0,
                    "path_type": "read",
                },
                {
                    "source": "stream-router",
                    "target": "object-origin",
                    "protocol": "https",
                    "latency_overhead_ms": 8.0,
                    "path_type": "both",
                },
            ],
            "workload": {
                "requests_per_second": 3000.0,
                "read_ratio": 0.96,
                "write_ratio": 0.04,
                "duration_seconds": 10,
                "burst_multiplier": 2.5,
            },
            "constraints": {
                "max_p95_latency_ms": 90.0,
                "min_throughput_rps": 2800.0,
                "max_cost_per_hour": 2.50,
            },
        },
    },
    "three_tier": {
        "id": "three_tier",
        "name": "Basic Three-Tier Enterprise Web Application",
        "description": "Standard classic enterprise web pattern featuring reverse proxy load balancer, application server pool, and relational database.",
        "architecture": {
            "architecture_id": "arch-three-tier-04",
            "components": [
                {
                    "id": "nginx-ingress",
                    "type": "load_balancer",
                    "name": "NGINX Reverse Proxy",
                    "capacity_rps": 3000.0,
                    "replicas": 1,
                    "base_latency_ms": 2.5,
                    "cost_per_month_usd": 30.0,
                },
                {
                    "id": "app-server",
                    "type": "api_server",
                    "name": "Enterprise App Worker Pool",
                    "capacity_rps": 900.0,
                    "replicas": 2,
                    "base_latency_ms": 16.0,
                    "cost_per_month_usd": 90.0,
                },
                {
                    "id": "sql-primary",
                    "type": "database",
                    "name": "MySQL Relational Cluster",
                    "capacity_rps": 700.0,
                    "replicas": 1,
                    "base_latency_ms": 28.0,
                    "cost_per_month_usd": 130.0,
                },
            ],
            "connections": [
                {
                    "source": "nginx-ingress",
                    "target": "app-server",
                    "protocol": "http",
                    "latency_overhead_ms": 1.2,
                    "path_type": "both",
                },
                {
                    "source": "app-server",
                    "target": "sql-primary",
                    "protocol": "sql",
                    "latency_overhead_ms": 2.5,
                    "path_type": "both",
                },
            ],
            "workload": {
                "requests_per_second": 850.0,
                "read_ratio": 0.75,
                "write_ratio": 0.25,
                "duration_seconds": 10,
                "burst_multiplier": 1.8,
            },
            "constraints": {
                "max_p95_latency_ms": 150.0,
                "min_throughput_rps": 800.0,
                "max_cost_per_hour": 1.20,
            },
        },
    },
}


def list_presets() -> List[Dict[str, Any]]:
    """Return summary list of all available presets."""
    return [
        {
            "id": preset["id"],
            "name": preset["name"],
            "description": preset["description"],
            "component_count": len(preset["architecture"]["components"]),
            "connection_count": len(preset["architecture"]["connections"]),
            "default_rps": preset["architecture"]["workload"]["requests_per_second"],
        }
        for preset in SYSTEM_PRESETS.values()
    ]


def get_preset(preset_id: str) -> Dict[str, Any] | None:
    """Return complete architecture definition for a preset."""
    return SYSTEM_PRESETS.get(preset_id)
