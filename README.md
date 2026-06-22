# CR-SHE: Collusion-Resilient Searchable Homomorphic Encryption

> Official implementation of **"Collusion-Resilient Searchable Homomorphic Encryption for Multi-Cloud IoT Data Sharing"** (IEEE Internet of Things Journal).

**CR-SHE** is a hybrid cryptographic framework designed for privacy-preserving, multi-cloud IoT data sharing. It addresses the unique threat of *cross-cloud collusion* by distributing a replicated, pseudonymous keyword index through a Distributed Point Function (DPF) and storing computable record fields under Leveled Homomorphic Encryption (HE, via Paillier). 

This architecture allows an authorized user to perform keyword retrievals and homomorphic analytics on retrieved ciphertexts without any decryption by—or at—the cloud providers, ensuring that a colluding coalition of up to `n-1` providers learns nothing about the queried keyword or access pattern.

---

## Repository Structure

*   **`crshe.py`**: The core logic. Handles indexing, PRF-pseudonymous address generation, and Paillier homomorphic aggregations (sum, mean, inner product).
*   **`dpf.py`**: Implementation of the Two-Party Distributed Point Function (BGI16 GGM-tree construction) using a SHA-256-based pseudorandom generator.
*   **`dataset_bench.py`**: Evaluates keyword search latency and communication overhead (DPF key size) against the real Reuters-21578 text corpus.
*   **`sensor_bench.py`**: Evaluates homomorphic compute latency across varying telemetry window sizes using real Mauna Loa atmospheric CO2 sensor data.
*   **`bench.py`**: General benchmarking scripts for base search and compute evaluations.
*   **`requirements.txt`**: Standard Python dependencies required to run the environment.
*   **`Figures/`**: Output directory where all generated `.pdf` and `.png` plots are securely saved.

---

## Quick Start (Windows PowerShell)

To set up the environment and run all benchmarks from scratch, open your PowerShell terminal in the project directory and execute the following commands in order:

```powershell
# 1. (Optional) Remove any existing virtual environment for a clean slate
Remove-Item -Recurse -Force .\venv

# 2. Create a new virtual environment named 'venv'
python -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\activate

# 4. Upgrade pip to the latest version
python -m pip install --upgrade pip

# 5. Install all project dependencies
pip install -r requirements.txt

# 6. Download the required NLTK 'reuters' dataset 
python -c "import nltk; nltk.download('reuters')"

# 7. Run the core cryptographic unit tests
python .\dpf.py
python .\crshe.py

# 8. Run the evaluation benchmarks
python sensor_bench.py
python dataset_bench.py
