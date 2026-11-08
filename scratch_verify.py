import asyncio
import json
from backend.ai_agent.architecture_parser import ArchitectureParserService
from backend.ai_agent.root_cause import RootCauseInvestigator
from backend.api.service import run_simulation
from backend.shared.adapter import adapt_m1_architecture_to_m2, adapt_m2_simulation_to_m1_baseline
from backend.config import settings

async def main():
    img_path = r"C:\Users\akash\Downloads\System_Design_check.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    print("Model ID in settings:", settings.gemini_model_id)
    svc = ArchitectureParserService()
    res = await svc.analyze_architecture(image_bytes=img_bytes)
    print("Fallback used:", res.fallback_used)
    print("Status:", res.status)
    print("Model ID used:", res.model_id)
    print("Provider used:", res.provider)
    if res.validation:
        print("Validation valid:", res.validation.valid)
        print("Validation issues:", [i.message for i in res.validation.issues])

    if res.architecture:
        nodes = [c.id for c in res.architecture.components]
        print(f"\nComponents extracted ({len(nodes)}):", nodes)
        print("Component details:")
        for c in res.architecture.components:
            print(f"  - {c.id} ({c.type}): attrs={c.attributes}")
        print("Connections:", [(conn.source, conn.target) for conn in res.architecture.connections])
        print("Workload:", res.architecture.workload)

        m2_graph, m2_workload, m2_constraints = adapt_m1_architecture_to_m2(res.architecture)
        sim_res = run_simulation(m2_graph, m2_workload, m2_constraints)
        print("\n--- Simulation Results ---")
        print("P95 Latency:", sim_res.metrics.p95_latency_ms)
        print("Throughput RPS:", sim_res.metrics.throughput_rps)
        print("Bottlenecks:", [b.component_id for b in sim_res.bottlenecks])
        print("Bottlenecks detail:")
        for b in sim_res.bottlenecks:
            print(f"  {b.component_id}: {b.reason}")

        investigator = RootCauseInvestigator()
        diag_res = investigator.start_investigation(
            architecture=res.architecture,
            baseline_result=adapt_m2_simulation_to_m1_baseline("run-01", sim_res, res.architecture)
        )
        print("\n--- Root Cause Hypotheses ---")
        for h in diag_res.hypotheses:
            print(f"[{h.status}] {h.title}: {h.affected_components} (conf: {h.confidence})")
        print("\nSynthesized Evidence Summary:")
        print(diag_res.synthesized_evidence)

if __name__ == "__main__":
    asyncio.run(main())

