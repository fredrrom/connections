from connections.utils.primitives import Variable, Expression

class Substitution:
    """
    Union-Find w. backtracking
    """
    def __init__(self):
        self.parent = {}
        self.rank = {}
        self.trail = []

    def find(self, item):
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1, item2):
        root1 = self.find(item1)
        root2 = self.find(item2)

        if root1 != root2:
            # Use rank to determine which tree becomes the parent
            if self.rank[root1] > self.rank[root2]:
                self.trail.append((root2, self.parent[root2]))
                self.parent[root2] = root1
            elif self.rank[root1] < self.rank[root2]:
                self.trail.append((root1, self.parent[root1]))
                self.parent[root1] = root2
            else:
                self.trail.append((root2, self.parent[root2]))
                self.parent[root2] = root1
                self.trail.append((root1, self.rank[root1]))
                self.rank[root1] += 1

    def add_substitution(self, var, term):
        self.union(var, term)

    def __call__(self, var):
        root = self.find(var)
        return root if root != var else None

    def backtrack(self):
        while self.trail:
            var, old_state = self.trail.pop()
            if isinstance(old_state, int):  # rank update
                self.rank[var] = old_state
            else:  # parent update
                self.parent[var] = old_state

    def get_final_substitutions(self):
        substitutions = {}
        for var in self.parent:
            if isinstance(var, Variable):
                term = self.find(var)
                if term != var:
                    substitutions[var] = term
        return substitutions

def occurs_check(var, term, subst):
    if var == term:
        return True
    if isinstance(term, Variable):
        term_root = subst.find(term)
        return occurs_check(var, term_root, subst) if term_root != term else False
    if isinstance(term, Expression):
        return any(occurs_check(var, arg, subst) for arg in term.args)
    return False

def unify(term1, term2, subst):
    term1 = subst.find(term1)
    term2 = subst.find(term2)

    if term1 == term2:
        return True

    if isinstance(term1, Variable):
        if occurs_check(term1, term2, subst):
            return False
        subst.add_substitution(term1, term2)
        return True

    if isinstance(term2, Variable):
        if occurs_check(term2, term1, subst):
            return False
        subst.add_substitution(term2, term1)
        return True

    if isinstance(term1, Expression) and isinstance(term2, Expression):
        if term1.functor != term2.functor or len(term1.args) != len(term2.args):
            return False
        for arg1, arg2 in zip(term1.args, term2.args):
            if not unify(arg1, arg2, subst):
                subst.backtrack()  # Roll back on failure
                return False
        return True

    return False

# Example usage with backtracking and rank
subst = Substitution()
X = Variable('X')
Y = Variable('Y')
term1 = Expression('f', [Expression('a'), X])
term2 = Expression('f', [Y, Expression('g', [Expression('b')])])

if unify(term1, term2, subst):
    substitutions = subst.get_final_substitutions()
    print(substitutions)  # Expected output: {X: g(b), Y: a}
else:
    print("Unification failed")
