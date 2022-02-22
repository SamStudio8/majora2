COG-UK Elan Minimal QC
Minimal ILL
2	2020-04-21
R	breadth_confidence	-	sequence	pc_masked	-	-	-	50
R	contiguity_confidence	-	sequence	longest_ungap	-	-	10000	-
R	mean_depth	-	mapping	mean_cov	-	-	10	-
R	depth_confidence	-	mapping	pc_pos_cov_gte10	-	-	50	-
D	breadth_confidence	AND	contiguity_confidence
D	mean_depth
D	depth_confidence
F	technology	-	sequencing	platform	ILLUMINA	EQ
