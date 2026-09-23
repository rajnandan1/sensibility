# Sensibility

A Claude Code plugin that lets Claude ask TypeSafe's Jev model for typed judgments during its own work. These are the words the plugin, its tickets, and its docs use.

## Language

### Jev's terms, adopted as is

**Jev**:
TypeSafe AI's System One model: it returns typed answers with probabilities to questions about a state, and generates no text.
_Avoid_: TypeSafe (the company), the judge model, the classifier

**State**:
The text or JSON that one request asks Jev to judge; every question in the request sees the same state.
_Avoid_: context, input, document, prompt

**Question**:
One typed judgment about the state: a Noul, a Choice, or a Score, with instructions and criteria.
_Avoid_: prompt, query, check

**Noul**:
A yes/no question whose answer is the probability, 0 to 1, that the answer is yes.
_Avoid_: boolean, flag, predicate

**Choice**:
A question that picks one option from a set the caller defines, returning the option and a probability per option.
_Avoid_: classification, label, enum

**Score**:
A question that places the state on ordered levels the caller describes, returning a probability-weighted position.
_Avoid_: rating, grade, rank

**Answer**:
The typed value Jev returns for one question, under the question's id.
_Avoid_: result, output, response (the response is the whole reply)

**Confidence**:
Jev's summary of how peaked a Choice or Score answer's probabilities are; Nouls have none.
_Avoid_: certainty, accuracy, correctness

### Sensibility's terms

**Judgment**:
One request to Jev: a state plus one or more questions, and the answers that come back together.
_Avoid_: evaluation, call, query, eval

**Battery**:
A named, reusable set of questions written for a described kind of state, optionally with a gate.
_Avoid_: preset, template, rubric, prompt pack

**Gate**:
The threshold policy, declared alongside a battery, that turns a judgment's answers into one of act, confirm, or escalate.
_Avoid_: threshold (that is one number inside a gate), filter, guard, policy

**Finish gate**:
The gate that judges whether Claude's reply at the end of a turn stops short of what the user asked, and nudges it to carry on.
_Avoid_: stop hook, completion check, stopping-short detector

**Risk gate**:
The gate that judges how irreversible and far-reaching a shell command is before it runs, and escalates risky ones to the user.
_Avoid_: safety hook, bash guard, risk score

**Taste**:
A battery made of Score questions over quality dimensions, whose answers say how good something is, not whether it is allowed.
_Avoid_: quality check, review, grade
