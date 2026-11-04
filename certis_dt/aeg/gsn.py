"""
Goal Structuring Notation (GSN) Metamodel and Assurance DAG.

Implements the SCSC GSN Standard v3 / OMG SACM 2.0 for safety and airworthiness
assurance cases, supporting automated hierarchical status evaluation and
Mermaid/JSON rendering.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import json


class GSNNodeType(Enum):
    GOAL = "Goal"
    STRATEGY = "Strategy"
    CONTEXT = "Context"
    ASSUMPTION = "Assumption"
    SOLUTION = "Solution"  # Evidence node


class GSNStatus(Enum):
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    DISQUALIFIED_REFUSED = "DISQUALIFIED_REFUSED"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class GSNNode:
    node_id: str
    node_type: GSNNodeType
    statement: str
    description: str = ""
    status: GSNStatus = GSNStatus.UNRESOLVED
    evidence_payload: Dict[str, Any] = field(default_factory=dict)
    children_ids: List[str] = field(default_factory=list)
    context_ids: List[str] = field(default_factory=list)


class GSNAssuranceCase:
    """
    Hierarchical Assurance Argument Directed Acyclic Graph (DAG).
    """

    def __init__(self, case_id: str = "CASE-CERTIS-DT-001", title: str = "CERTIS-DT Airworthiness Case"):
        self.case_id = case_id
        self.title = title
        self.nodes: Dict[str, GSNNode] = {}
        self.root_goal_id: Optional[str] = None

    def add_node(self, node: GSNNode, is_root: bool = False) -> None:
        """Add a node to the assurance case."""
        self.nodes[node.node_id] = node
        if is_root or self.root_goal_id is None:
            if node.node_type == GSNNodeType.GOAL and is_root:
                self.root_goal_id = node.node_id

    def add_relationship(self, parent_id: str, child_id: str) -> None:
        """Link parent to child node in the argument tree."""
        if parent_id in self.nodes and child_id in self.nodes:
            if child_id not in self.nodes[parent_id].children_ids:
                self.nodes[parent_id].children_ids.append(child_id)

    def add_context_link(self, target_node_id: str, context_node_id: str) -> None:
        """Link a context/assumption node to a goal or strategy."""
        if target_node_id in self.nodes and context_node_id in self.nodes:
            if context_node_id not in self.nodes[target_node_id].context_ids:
                self.nodes[target_node_id].context_ids.append(context_node_id)

    def evaluate_tree(self) -> GSNStatus:
        """
        Recursively evaluate assurance tree status from leaves (solutions) to root goal.
        """
        if not self.root_goal_id or self.root_goal_id not in self.nodes:
            return GSNStatus.UNRESOLVED
            
        def eval_node(nid: str) -> GSNStatus:
            node = self.nodes[nid]
            if node.node_type == GSNNodeType.SOLUTION:
                return node.status
            if node.node_type in (GSNNodeType.CONTEXT, GSNNodeType.ASSUMPTION):
                return GSNStatus.SATISFIED
                
            if not node.children_ids:
                return node.status
                
            child_statuses = [eval_node(cid) for cid in node.children_ids]
            
            # Any violation violates parent
            if any(s == GSNStatus.VIOLATED for s in child_statuses):
                node.status = GSNStatus.VIOLATED
            elif any(s == GSNStatus.DISQUALIFIED_REFUSED for s in child_statuses):
                node.status = GSNStatus.DISQUALIFIED_REFUSED
            elif all(s == GSNStatus.SATISFIED for s in child_statuses):
                node.status = GSNStatus.SATISFIED
            else:
                node.status = GSNStatus.UNRESOLVED
                
            return node.status

        return eval_node(self.root_goal_id)

    def to_mermaid(self) -> str:
        """
        Export assurance case to standard GitHub Flavored Mermaid diagram.
        """
        lines = ["flowchart TD"]
        
        # Style definitions
        lines.append("    classDef goalStyle fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#ffffff;")
        lines.append("    classDef stratStyle fill:#374151,stroke:#9ca3af,stroke-width:2px,stroke-dasharray: 4 2,color:#ffffff;")
        lines.append("    classDef solPass fill:#065f46,stroke:#10b981,stroke-width:2px,color:#ffffff;")
        lines.append("    classDef solFail fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#ffffff;")
        lines.append("    classDef solRefuse fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#ffffff;")
        lines.append("    classDef ctxStyle fill:#1f2937,stroke:#6b7280,stroke-width:1px,color:#d1d5db;")
        
        # Render nodes
        for nid, node in self.nodes.items():
            safe_text = node.statement.replace('"', "'")
            status_tag = f" [{node.status.value}]" if node.node_type in (GSNNodeType.GOAL, GSNNodeType.SOLUTION) else ""
            label = f'"{nid}: {safe_text}{status_tag}"'
            
            if node.node_type == GSNNodeType.GOAL:
                lines.append(f"    {nid}[{label}]:::goalStyle")
            elif node.node_type == GSNNodeType.STRATEGY:
                lines.append(f"    {nid}({label}):::stratStyle")
            elif node.node_type == GSNNodeType.SOLUTION:
                cls_name = "solPass" if node.status == GSNStatus.SATISFIED else ("solRefuse" if node.status == GSNStatus.DISQUALIFIED_REFUSED else "solFail")
                lines.append(f"    {nid}([{label}]):::{cls_name}")
            elif node.node_type in (GSNNodeType.CONTEXT, GSNNodeType.ASSUMPTION):
                lines.append(f"    {nid}> {label} ]:::ctxStyle")

        # Render edges
        for nid, node in self.nodes.items():
            for cid in node.children_ids:
                lines.append(f"    {nid} --> {cid}")
            for ctxt_id in node.context_ids:
                lines.append(f"    {nid} -.-> {ctxt_id}")

        return "\n".join(lines)

    def to_sacm_json(self) -> str:
        """Export to OMG Structured Assurance Case Metamodel (SACM) compliant JSON."""
        data = {
            "sacm_version": "2.0",
            "case_id": self.case_id,
            "title": self.title,
            "overall_status": self.evaluate_tree().value,
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.node_type.value,
                    "statement": n.statement,
                    "description": n.description,
                    "status": n.status.value,
                    "children": n.children_ids,
                    "context": n.context_ids,
                    "evidence_payload": n.evidence_payload,
                }
                for n in self.nodes.values()
            ],
        }
        return json.dumps(data, indent=2)
