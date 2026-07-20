"""Import-isolated output for PDS2 printable-response commands."""

from quillan.printable_response_generation import GeneratedPrintableResponsePacket
from quillan.printable_response_packet import PrintableResponsePacketPlan


def _bool(value: bool) -> str:
    return "yes" if value else "no"


def print_printable_response_packet_plan(plan: PrintableResponsePacketPlan) -> None:
    print("Printable response packet dry run:")
    print(f"Class: {plan.class_id}")
    print(f"Assignment: {plan.assignment_id} - {plan.assignment_title}")
    print(f"Students: {plan.student_count}")
    print(f"Planned issuances: {plan.planned_issuance_count}")
    print(f"Pages per student: {plan.pages_per_student}")
    print(f"Total packet pages: {plan.total_page_count}")
    print(f"Planned routes: {plan.planned_route_count}")
    print(f"Predecessors: {plan.predecessor_count}")
    print(f"Initial issuances: {plan.initial_issuance_count}")
    print(f"Regeneration issuances: {plan.regeneration_issuance_count}")
    print(f"Assignment config: {plan.assignment_relative_path}")
    print(f"Roster: {plan.roster_relative_path}")
    print(f"Would write: {plan.output_relative_path}")
    print(f"Existing target: {_bool(plan.target_exists)}")
    if plan.target_exists:
        print("Replacement requires --overwrite --yes during actual generation.")
    print("No files were written.")


def print_generated_printable_response_packet(
    result: GeneratedPrintableResponsePacket,
) -> None:
    print(
        "Generated printable response packet:"
        if result.success
        else "Printable response packet result:"
    )
    print(f"Class: {result.class_id}")
    print(f"Assignment: {result.assignment_id} - {result.assignment_title}")
    print(f"Students: {result.student_count}")
    print(f"Pages per student: {result.pages_per_student}")
    print(f"Total packet pages: {result.physical_page_count}")
    print(f"Planned routes: {result.planned_route_count}")
    print(f"Created routes: {result.created_route_count}")
    print(f"Verified routes: {result.verified_route_count}")
    print(f"Installed: {_bool(result.installed)}")
    if result.installed:
        action = "replaced existing packet" if result.replaced_existing else "created"
        print(f"Action: {action}")
    if result.partial_success:
        print("Status: INSTALLED PARTIAL FAILURE")
    elif not result.success:
        print("Status: FAILED BEFORE INSTALLATION")
    if result.failure_stage is not None:
        print(f"Failure stage: {result.failure_stage}")
    if result.error is not None:
        print(f"Error: {result.error}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(f"PDF: {result.output_relative_path}")


__all__ = [
    "print_generated_printable_response_packet",
    "print_printable_response_packet_plan",
]
