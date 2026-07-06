"""OWL/RDF ontology import via owlready2."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from knowledge_graph_foundry.types.ontology import PropertyDef, RelationshipDef, TypeDef


def import_owl(
    path: Path,
    max_depth: int = 2,
    branch_filter: str | None = None,
) -> tuple[list[TypeDef], list[RelationshipDef]]:
    """Import entity types and relationship types from an OWL/RDF file.

    Maps OWL concepts to kg-builder types:
    - owl:Class -> TypeDef (with rdfs:comment as description)
    - rdfs:subClassOf -> TypeDef.parent
    - owl:ObjectProperty -> RelationshipDef (domain -> source, range -> target)
    - owl:DatatypeProperty -> PropertyDef attached to domain type
    - owl:disjointWith -> logged as advisory warning

    Args:
        path: Path to .owl/.rdf/.ttl file
        max_depth: Maximum subclass depth to import
        branch_filter: If set, only import classes under this branch

    Returns:
        Tuple of (entity_types, relationship_types)
    """
    import owlready2

    onto = owlready2.get_ontology(str(path.resolve().as_uri())).load()

    # Build class hierarchy depth map
    depth_map: dict[str, int] = {}
    _compute_depths(onto, depth_map)

    # Collect entity types from owl:Class
    entity_types: dict[str, TypeDef] = {}
    for cls in onto.classes():
        name = cls.name
        depth = depth_map.get(name, 0)

        if depth > max_depth:
            continue

        if branch_filter and not _is_under_branch(cls, branch_filter):
            continue

        # Get parent (first named superclass that is in our ontology)
        parent = None
        for sup in cls.is_a:
            if hasattr(sup, "name") and sup.name != name and sup is not owlready2.Thing:
                parent = sup.name
                break

        description = ""
        if cls.comment:
            description = str(cls.comment[0])

        entity_types[name] = TypeDef(
            name=name,
            description=description,
            parent=parent,
        )

    # Collect datatype properties and attach to entity types
    for prop in onto.data_properties():
        prop_name = prop.name
        description = str(prop.comment[0]) if prop.comment else ""

        # Determine property type from range
        prop_type = "string"
        if prop.range:
            range_type = str(prop.range[0])
            if "float" in range_type or "double" in range_type or "decimal" in range_type:
                prop_type = "number"
            elif "integer" in range_type or "int" in range_type:
                prop_type = "integer"
            elif "boolean" in range_type:
                prop_type = "boolean"

        prop_def = PropertyDef(
            name=prop_name,
            type=prop_type,
            description=description,
        )

        # Attach to domain classes
        for domain_cls in prop.domain:
            if hasattr(domain_cls, "name") and domain_cls.name in entity_types:
                entity_types[domain_cls.name].property_defs.append(prop_def)

    # Collect relationship types from owl:ObjectProperty
    relationship_types: list[RelationshipDef] = []
    for prop in onto.object_properties():
        prop_name = prop.name
        description = str(prop.comment[0]) if prop.comment else ""

        source_type = ""
        if prop.domain:
            for d in prop.domain:
                if hasattr(d, "name"):
                    source_type = d.name
                    break

        target_type = ""
        if prop.range:
            for r in prop.range:
                if hasattr(r, "name"):
                    target_type = r.name
                    break

        relationship_types.append(
            RelationshipDef(
                name=prop_name,
                source_type=source_type,
                target_type=target_type,
                description=description,
            )
        )

    # Log disjoint warnings
    for cls in onto.classes():
        if hasattr(cls, "disjoints"):
            for disj in cls.disjoints():
                names = [c.name for c in disj.entities if hasattr(c, "name")]
                if len(names) >= 2:
                    logger.info(
                        "OWL advisory: disjoint classes {} (not enforced)",
                        ", ".join(names),
                    )

    logger.info(
        "OWL import: {} entity types, {} relationship types from {}",
        len(entity_types),
        len(relationship_types),
        path.name,
    )
    return list(entity_types.values()), relationship_types


def _compute_depths(onto, depth_map: dict[str, int]) -> None:
    """Compute depth of each class from root (Thing)."""
    import owlready2

    for cls in onto.classes():
        if cls.name not in depth_map:
            _class_depth(cls, depth_map, owlready2.Thing)


def _class_depth(cls, depth_map: dict[str, int], thing_cls) -> int:
    """Recursive depth calculation with memoization."""
    if cls.name in depth_map:
        return depth_map[cls.name]

    parents = [sup for sup in cls.is_a if hasattr(sup, "name") and sup is not thing_cls]

    if not parents:
        depth_map[cls.name] = 0
        return 0

    max_parent_depth = max(_class_depth(p, depth_map, thing_cls) for p in parents)
    depth_map[cls.name] = max_parent_depth + 1
    return max_parent_depth + 1


def _is_under_branch(cls, branch_name: str) -> bool:
    """Check if cls is the branch root or a descendant of it."""
    if cls.name == branch_name:
        return True
    for ancestor in cls.ancestors():
        if hasattr(ancestor, "name") and ancestor.name == branch_name:
            return True
    return False
