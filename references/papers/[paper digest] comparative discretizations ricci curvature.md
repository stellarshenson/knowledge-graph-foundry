**Comparative Analysis of Two Discretizations of Ricci Curvature for Complex Networks (2018, Sci Rep)**

An empirical comparison of Forman-Ricci and Ollivier-Ricci curvature across model and real-world networks finds the two discretizations are **highly correlated in many networks**, and that correlation rises **even higher once Forman curvature is augmented with the two-dimensional simplicial complexes (triangles) that arise in graphs**. Plain Forman curvature, lacking the triangle term, tracks Ollivier-Ricci less faithfully than the augmented version.

**Key mechanism**
- Computes both Forman-Ricci and Ollivier-Ricci curvature on the same set of model and real networks
- Compares plain Forman-Ricci against an augmented Forman-Ricci that also counts triangles (2-simplices)
- Measures correlation between the two discretizations under each variant

**Main findings**
- Forman-Ricci and Ollivier-Ricci curvature are highly correlated across many networks despite arising from different mathematical properties of the smooth Ricci notion
- Adding the triangle-count augmentation to Forman curvature increases its correlation with Ollivier-Ricci, especially in real networks
- Plain (un-augmented) Forman curvature can substitute for the costlier Ollivier-Ricci computation for coarse analysis on large networks, but the triangle term is what closes the gap

**Key takeaways**
- Isolates the triangle term as the specific mechanism that carries information beyond degree - on a triangle-poor graph (star-forest-like structure), plain Forman curvature has nothing else to draw on and reduces to a degree signal
- Directly supports the H544 kill: if the corpus graph region under test is triangle-sparse, plain Forman curvature is expected to degenerate to degree, exactly as this paper's mechanism predicts
- Sets up the case for AFRC (augmented Forman-Ricci) as the instrument that actually recovers Ollivier-Ricci-like discriminative power

**Tags**
- #GraphCurvature #FormanRicci #OllivierRicci #ComplexNetworks

**Source**
- Download: https://arxiv.org/pdf/1712.07600
- Local: [paper] comparative discretizations ricci curvature, 2018.pdf
