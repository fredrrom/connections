from cops.utils.cnf_parsing import file2cnf


class TestCNFParsingSYN:
    # ARRANGE
    m = '[[q(f_skolem(3), f_skolem(4))], [p(f_skolem(1), f_skolem(2))], [-p(_192, _196), p(_192, _194), p(_194, _196)], [-q(_276, _280), q(_276, _278), q(_278, _280)], [q(_360, _362), -q(_362, _360)], [-p(_418, _430), -q(_418, _430)]]'
    r = file2cnf('tests/cnf_problems/SYN726+1.cnf')

    def test_file2cnf_print(self):
        # ASSERT
        assert str(self.r.clauses) == self.m

    def test_file2cnf_clauses(self):
        # ASSERT
        assert len(self.r.clauses) == 6

class TestCNFParsingCSR:
    # ARRANGE
    r = file2cnf('tests/cnf_problems/CSR091+1.p.cnf')
    print(r)

    def test_file2cnf_clauses_csr(self):
        # ASSERT
        assert len(self.r.clauses) == 16384
