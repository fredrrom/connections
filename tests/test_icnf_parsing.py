from cops.utils.icnf_parsing import file2cnf

"""
class TestICNFParsing:
    # ARRANGE
    m = '[[big_f(_3436), -big_f(f(_3436))], [big_f(_2806), big_f(f(_2806))], [-big_f(f(_2806)), -big_f(_2806)]]'
    r = file2cnf('tests/icnf_problems/SYN081+1.cnf')

    def test_file2cnf_print(self):
        # ASSERT
        assert str(self.r.clauses) == self.m

    def test_file2cnf_clauses(self):
        # ASSERT
        assert len(self.r.clauses) == 3

    def test_file2cnf_second_prefix(self):
        # ASSERT
        assert str(self.r.clauses[0][1].prefix[0]) == 'c_skolem(8, _3436)'
        assert len(self.r.clauses[0][1].prefix) == 1
"""