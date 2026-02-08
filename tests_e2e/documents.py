"""Synthetic test documents for e2e testing.

Each document is carefully crafted for chunk_size=50, overlap=0.3 (step=35).
Word counts are exact so that chunk boundaries are deterministic.

Document 1: 70 words -> 2 chunks
    Chunk 1: words[0:50]   (50 words)
    Chunk 2: words[35:70]  (35 words)
    Overlap:  words[35:50]  (15 words)

    Unique-to-chunk-1 keywords: superposition, chloroplasts (words 0-34)
    Overlap keywords:           entanglement               (words 35-49)
    Unique-to-chunk-2 keywords: topological                (words 50-69)

Document 2: 105 words -> 3 chunks
    Chunk 1: words[0:50]   (50 words)
    Chunk 2: words[35:85]  (50 words)
    Chunk 3: words[70:105] (35 words)
    Overlap 1-2: words[35:50] (15 words)
    Overlap 2-3: words[70:85] (15 words)

    Unique-to-chunk-1 keywords: symbiotic, zooxanthellae   (words 0-34)
    Overlap-1-2 keywords:       acidification               (words 35-49)
    Unique-to-chunk-2 keywords: bioluminescence             (words 50-69)
    Overlap-2-3 keywords:       hydrothermal                (words 70-84)
    Unique-to-chunk-3 keywords: chemosynthetic              (words 85-104)
"""

# ---------- chunk config used by e2e tests ----------
E2E_CHUNK_SIZE = 50
E2E_OVERLAP = 0.3

# ---------- Document 1 (70 words -> 2 chunks) ----------
DOCUMENT_1 = (
    "Quantum computing harnesses the principles of quantum mechanics to perform"
    " calculations that would be impossible for classical computers Unlike"
    " traditional bits that exist as zero or one quantum bits called qubits can"
    " exist in superposition representing both values simultaneously This"
    " enables quantum entanglement experiments where particles become correlated"
    " across vast distances The field now pursues quantum error correction using"
    " topological codes to protect fragile quantum states from harmful"
    " environmental decoherence"
)

# Keywords unique to chunk 1 (indices 0-34)
DOC1_CHUNK1_UNIQUE = "superposition"
# Keywords in the overlap region (indices 35-49)
DOC1_OVERLAP = "entanglement"
# Keywords unique to chunk 2 (indices 50-69)
DOC1_CHUNK2_UNIQUE = "topological"

# ---------- Document 2 (105 words -> 3 chunks) ----------
DOCUMENT_2 = (
    "Coral reefs are among the most biodiverse ecosystems on Earth providing"
    " habitat for thousands of marine species The intricate symbiotic"
    " relationship between coral polyps and zooxanthellae algae creates the"
    " foundation for these underwater cities Reef structures protect coastlines"
    " from erosion however increasing ocean acidification caused by carbon"
    " dioxide absorption threatens these delicate formations Meanwhile deep"
    " ocean creatures display remarkable bioluminescence producing light through"
    " chemical reactions within specialized organs called photophores These"
    " adaptations evolved near hydrothermal vents where superheated water rich"
    " in minerals erupts from the seafloor creating unique ecosystems"
    " Independent of sunlight these vent communities rely on chemosynthetic"
    " bacteria converting toxic hydrogen sulfide into energy"
)

# Keywords unique to chunk 1 (indices 0-34)
DOC2_CHUNK1_UNIQUE = "symbiotic"
# Keywords in overlap 1-2 (indices 35-49)
DOC2_OVERLAP_12 = "acidification"
# Keywords unique to chunk 2 (indices 50-69)
DOC2_CHUNK2_UNIQUE = "bioluminescence"
# Keywords in overlap 2-3 (indices 70-84)
DOC2_OVERLAP_23 = "hydrothermal"
# Keywords unique to chunk 3 (indices 85-104)
DOC2_CHUNK3_UNIQUE = "chemosynthetic"
