from cops.utils.cnf_parsing import file2cnf


class TestCNFParsingSYN:
    # ARRANGE
    m = '[[q(f_skolem(3), f_skolem(4))], [p(f_skolem(1), f_skolem(2))], [-p(_4075, _4186), p(_4075, _4131), ' \
        'p(_4131, _4186)], [-q(_4468, _4579), q(_4468, _4524), q(_4524, _4579)], [q(_4861, _4906), -q(_4906, ' \
        '_4861)], [-p(_5087, _5132), -q(_5087, _5132)]]'
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
