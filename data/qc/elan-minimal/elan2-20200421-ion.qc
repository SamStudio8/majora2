COG-UK Elan Minimal QC
Minimal ION
2	2021-04-16
R	breadth_confidence	-	sequence	pc_masked	-	-	-	50
R	contiguity_confidence	-	sequence	longest_ungap	-	-	10000	-
R	mean_depth	-	mapping	mean_cov	-	-	30	-
R	depth_confidence	-	mapping	pc_pos_cov_gte20	-	-	50	-
D	breadth_confidence	AND	contiguity_confidence
D	mean_depth
D	depth_confidence
F	technology	-	sequencing	platform	ION_TORRENT	EQ
