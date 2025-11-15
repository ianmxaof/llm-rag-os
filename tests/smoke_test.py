"""
Smoke Tests for RAG OS v0.1
----------------------------
Basic tests to verify core functionality works:
- Ollama API connectivity and embeddings
- FastAPI endpoints
- Streamlit availability
"""

import requests
import time
import os
from pathlib import Path

# Test configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
STREAMLIT_BASE = os.getenv("STREAMLIT_BASE", "http://localhost:8501")
OLLAMA_API = os.getenv("OLLAMA_API", "http://localhost:11434/api")


def test_health_endpoint():
    """Test FastAPI health endpoint."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Unexpected status: {data}"
        print("✅ Health endpoint test passed")
        return True
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False


def test_ollama_status():
    """Test Ollama status endpoint."""
    try:
        response = requests.get(f"{API_BASE}/ollama/status", timeout=5)
        assert response.status_code == 200, f"Ollama status check failed: {response.status_code}"
        data = response.json()
        print(f"✅ Ollama status test passed: {data.get('available', False)}")
        return True
    except Exception as e:
        print(f"❌ Ollama status test failed: {e}")
        return False


def test_ollama_load_unload():
    """Test Ollama embed_texts function (load → embed → unload)."""
    try:
        from backend.controllers.ollama import embed_texts
        
        test_texts = ["Hello world", "This is a test"]
        embeddings = embed_texts(test_texts, model="nomic-embed-text")
        
        assert len(embeddings) == 2, f"Expected 2 embeddings, got {len(embeddings)}"
        assert len(embeddings[0]) > 0, "Embedding should not be empty"
        assert isinstance(embeddings[0], list), "Embedding should be a list"
        
        print("✅ Ollama load/unload test passed")
        return True
    except Exception as e:
        print(f"❌ Ollama load/unload test failed: {e}")
        return False


def test_ingest_endpoint():
    """Test FastAPI ingest endpoint."""
    try:
        # Wait for FastAPI to be ready
        for _ in range(10):
            try:
                response = requests.get(f"{API_BASE}/health", timeout=2)
                if response.status_code == 200:
                    break
            except:
                time.sleep(3)
        
        # Create a test file
        test_file = Path("knowledge/inbox/test_smoke.md")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Test Document\n\nThis is a smoke test document.")
        
        # Test ingest endpoint
        response = requests.post(
            f"{API_BASE}/ingest/file",
            json={"path": str(test_file.resolve())},
            timeout=30
        )
        
        assert response.status_code == 200, f"Ingest endpoint failed: {response.status_code}"
        data = response.json()
        assert data.get("success") == True, f"Ingest failed: {data.get('message', 'Unknown error')}"
        
        # Cleanup
        if test_file.exists():
            test_file.unlink()
        
        print("✅ Ingest endpoint test passed")
        return True
    except Exception as e:
        print(f"❌ Ingest endpoint test failed: {e}")
        return False


def test_streamlit_up():
    """Test Streamlit is responding."""
    try:
        response = requests.get(STREAMLIT_BASE, timeout=10)
        assert response.status_code == 200, f"Streamlit not responding: {response.status_code}"
        assert "RAG Control Panel" in response.text or "streamlit" in response.text.lower(), "Unexpected Streamlit content"
        print("✅ Streamlit availability test passed")
        return True
    except Exception as e:
        print(f"❌ Streamlit availability test failed: {e}")
        return False


def run_all_tests():
    """Run all smoke tests."""
    print("=" * 50)
    print("Running Smoke Tests for RAG OS v0.1")
    print("=" * 50)
    
    results = []
    
    # Test 1: Health endpoint
    results.append(("Health Endpoint", test_health_endpoint()))
    
    # Test 2: Ollama status
    results.append(("Ollama Status", test_ollama_status()))
    
    # Test 3: Ollama embeddings
    results.append(("Ollama Load/Unload", test_ollama_load_unload()))
    
    # Test 4: Ingest endpoint
    results.append(("Ingest Endpoint", test_ingest_endpoint()))
    
    # Test 5: Streamlit
    results.append(("Streamlit Availability", test_streamlit_up()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

