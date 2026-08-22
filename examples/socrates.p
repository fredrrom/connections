% All men are mortal; Socrates is a man; therefore Socrates is mortal.
% SZS status: Theorem
fof(all_men_mortal, axiom, ![X] : (man(X) => mortal(X))).
fof(socrates_man,   axiom, man(socrates)).
fof(goal,           conjecture, mortal(socrates)).
