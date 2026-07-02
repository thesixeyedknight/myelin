"""Test RAG with adversarial queries to prevent hallucinations."""
import sys
sys.path.insert(0, ".")

from src.tools.rag_tools import index_document, query_knowledge, list_indexed_documents

def test_basic_indexing():
    """Test basic indexing and retrieval."""
    print("="*60)
    print("TEST 1: Basic Indexing & Retrieval")
    print("="*60)
    
    # Index a document
    result = index_document("data/test_rag/crispr_research.txt")
    print(f"\nIndexing result: {result}")
    
    if "error" in result:
        print(f"✗ FAILED: {result['error']}")
        return False
    
    print(f"✓ Indexed {result['chunks_indexed']} chunks")
    
    # Query for relevant information
    query_result = query_knowledge("What are CRISPR off-target rates?")
    print(f"\nQuery result: {query_result.get('total_results')} relevant chunks found")
    
    if query_result.get('warning'):
        print(f"⚠ Warning: {query_result['warning']}")
        return False
    
    # Print top result
    if query_result['results']:
        top = query_result['results'][0]
        print(f"\nTop result (score: {top['relevance_score']}):")
        print(f"  Chunk ID: {top['chunk_id']}")
        print(f"  Text preview: {top['text'][:100]}...")
    
    print("\n✓ Test 1 PASSED\n")
    return True

def test_hallucination_prevention():
    """Test adversarial query - ask about unrelated topic."""
    print("="*60)
    print("TEST 2: Hallucination Prevention (Adversarial)")
    print("="*60)
    
    # Query about something NOT in the indexed document
    query_result = query_knowledge("What does the document say about quantum computing?")
    print(f"\nQuerying about OFF-TOPIC subject (quantum computing)...")
    print(f"Total results: {query_result.get('total_results', 0)}")
    
    if query_result.get('warning'):
        print(f"✓ EXPECTED: System correctly warned - '{query_result['warning']}'")
        print("✓ Test 2 PASSED (No hallucination)\n")
        return True
    elif query_result.get('total_results', 0) > 0:
        print(f"✗ FAILED: System returned {query_result['total_results']} results for unrelated topic")
        print("   This indicates potential for hallucination!")
        return False
    else:
        print("✓ Test 2 PASSED\n")
        return True

def test_input_validation():
    """Test idiot-proofing - invalid inputs."""
    print("="*60)
    print("TEST 3: Input Validation (Idiot-Proofing)")
    print("="*60)
    
    tests = [
        ("Empty query", lambda: query_knowledge("")),
        ("Too vague query", lambda: query_knowledge("hi")),
        ("Nonexistent file", lambda: index_document("nonexistent.txt")),
    ]
    
    passed = 0
    for name, test_fn in tests:
        result = test_fn()
        if "error" in result:
            print(f"✓ {name}: Correctly rejected - '{result['error']}'")
            passed += 1
        else:
            print(f"✗ {name}: Should have been rejected!")
    
    if passed == len(tests):
        print(f"\n✓ Test 3 PASSED ({passed}/{len(tests)} validations)\n")
        return True
    else:
        print(f"\n✗ Test 3 FAILED ({passed}/{len(tests)} passed)\n")
        return False

def test_citation_metadata():
    """Test that results include proper citation metadata."""
    print("="*60)
    print("TEST 4: Citation Metadata")
    print("="*60)
    
    query_result = query_knowledge("What are the off-target rates mentioned?")
    
    if "error" in query_result or query_result.get('warning'):
        print(f"✗ FAILED: {query_result.get('error') or query_result.get('warning')}")
        return False
    
    # Check each result has required citation fields
    required_fields = ['chunk_id', 'metadata', 'relevance_score', 'text']
    all_valid = True
    
    for i, result in enumerate(query_result['results']):
        missing = [f for f in required_fields if f not in result]
        if missing:
            print(f"✗ Result {i}: Missing fields: {missing}")
            all_valid = False
        else:
            # Check metadata has source
            if 'source' not in result['metadata']:
                print(f"✗ Result {i}: Metadata missing 'source' field")
                all_valid = False
    
    if all_valid:
        print(f"✓ All {len(query_result['results'])} results have complete citation metadata")
        print(f"   Example chunk_id: {query_result['results'][0]['chunk_id']}")
        print("✓ Test 4 PASSED\n")
        return True
    else:
        print("✗ Test 4 FAILED\n")
        return False

def test_listing():
    """Test document listing."""
    print("="*60)
    print("TEST 5: Document Listing")
    print("="*60)
    
    result = list_indexed_documents()
    print(f"\nIndexed documents: {result.get('total_documents', 0)}")
    print(f"Total chunks: {result.get('total_chunks', 0)}")
    
    if result.get('documents'):
        for doc in result['documents']:
            print(f"  - {doc['source']}: {doc['chunks']} chunks")
    
    print("✓ Test 5 PASSED\n")
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("RAG ADVERSARIAL TESTING SUITE")
    print("="*60 + "\n")
    
    tests = [
        test_basic_indexing,
        test_hallucination_prevention,
        test_input_validation,
        test_citation_metadata,
        test_listing
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"✗ TEST CRASHED: {str(e)}\n")
            results.append(False)
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    passed_count = sum(results)
    total_count = len(results)
    print(f"Tests Passed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("✓ ALL TESTS PASSED - RAG is robust and hallucination-resistant")
    else:
        print("✗ SOME TESTS FAILED - Review failures above")
    
    print("="*60 + "\n")
