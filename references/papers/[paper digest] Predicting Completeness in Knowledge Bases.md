# Predicting Completeness in Knowledge Bases

**Authors**: Luis Galárraga, Simon Razniewski, Antoine Amarilli, Fabian Suchanek
**Published**: February 2017, WSDM 2017
**Original**: https://suchanek.name/work/publications/wsdm-2017.pdf
**Local copy**: `[paper] Predicting Completeness in Knowledge Bases, 2017-02.pdf`

## Problem

Knowledge bases operate under the open-world assumption: a missing fact is not a false fact. Nothing in the KB itself says whether an entity's property set is complete, so consumers cannot distinguish "has no children" from "children not yet recorded".

## Mechanism

Mines completeness signals and combines them via rule mining (AMIE-style association rules over completeness assertions):

- **Closed-world assumption** baseline, **popularity assumption** (popular entities are more complete), **partial completeness assumption** (if an entity has some objects for a property, it has all of them)
- Learned rules predict per-entity-per-property completeness, e.g. "a person with a death date has complete children"
- Obligatory attributes (every instance of the type must have one - bornIn, gender, nationality) are the high-precision target class

## Results

- 80% precision at 40% recall predicting completeness over all predicates on Wikidata and YAGO
- F1 90-100% for obligatory relations
- Single-valued properties are the most predictable targets

## Relevance to KGF

Direct grounding for R04-H23 (completeness audit): the type-cohort attribute-expectation mechanism ("if siblings of the type carry the attribute, an instance missing it is a detectable gap") is this paper's obligatory-attribute finding applied per use-case regime. KGF's twist: the detected gap drives repair-from-source rather than remaining an annotation.
