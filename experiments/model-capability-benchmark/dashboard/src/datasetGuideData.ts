export type DatasetStatus = 'current' | 'historical';
export type Difficulty = 'easy' | 'medium' | 'hard' | 'challenge';

export interface DatasetGuide {
  id: string;
  name: string;
  group: string;
  version?: number;
  status: DatasetStatus;
  origin: 'public' | 'repository-authored';
  capabilityIds: string[];
  caseCount: number | null;
  purpose: string;
  measures: string;
  metric: string;
  example: { input: string; output: string };
  families?: Array<{ label: string; count: number }>;
  difficulty?: Partial<Record<Difficulty, number>>;
  tiers?: { smoke: number; core: number; extended: number };
  caution: string;
}

const mathFamilies = [
  { label: 'Arithmetic', count: 12 },
  { label: 'Percentages', count: 12 },
  { label: 'Multi-step', count: 12 },
  { label: 'Algebra', count: 12 },
  { label: 'Logic', count: 12 },
  { label: 'Constraints', count: 12 },
];

export const datasetGuides: DatasetGuide[] = [
  {
    id: 'banking77', name: 'BANKING77', group: 'Banking intent', status: 'current',
    origin: 'public', capabilityIds: ['intent-classification', 'oos-calibration'],
    caseCount: null,
    purpose: 'Recognize the user’s banking intent among 77 labels.',
    measures: 'Correct intent label; also serves as in-scope examples for OOS calibration.',
    metric: 'Intent accuracy · in-scope calibration',
    example: { input: 'I need to withdraw cash from an ATM.', output: 'cash_withdrawal' },
    caution: 'The same dataset supports two different tasks. Classification accuracy and OOS-calibration metrics are not interchangeable. Sample counts depend on capability and profile.',
  },
  {
    id: 'clinc150-oos', name: 'CLINC150 · OOS', group: 'Out-of-scope', status: 'current',
    origin: 'public', capabilityIds: ['oos-calibration'], caseCount: null,
    purpose: 'Detect requests outside the banking intent taxonomy.',
    measures: 'Correct rejection of filtered out-of-scope prompts, together with reported confidence.',
    metric: 'OOS detection · calibration',
    example: { input: 'What is the weather tomorrow?', output: 'other' },
    tiers: { smoke: 40, core: 77, extended: 154 },
    caution: 'Only filtered CLINC150 out-of-scope prompts are used. These results alone do not measure general CLINC150 in-domain classification.',
  },
  {
    id: 'structured-output-controlled-v1', name: 'Structured output · v1', group: 'Structured output', version: 1,
    status: 'historical', origin: 'repository-authored', capabilityIds: ['structured-output'], caseCount: 2,
    purpose: 'Check elementary JSON field extraction and schema conformance.',
    measures: 'Exact fields in simple, flat records.',
    metric: 'Exact match',
    example: { input: 'Invoice from Acme Srl totals EUR 125.40.', output: '{"vendor":"Acme Srl","amount":125.4,"currency":"EUR"}' },
    caution: 'Minimal initial fixture, not a comprehensive difficulty or reliability benchmark.',
  },
  {
    id: 'structured-output-controlled-v2', name: 'Structured output · v2', group: 'Structured output', version: 2,
    status: 'current', origin: 'repository-authored', capabilityIds: ['structured-output'], caseCount: 60,
    purpose: 'Extract valid JSON across progressively less tidy inputs.',
    measures: 'Exact field values and schemas with nesting, arrays, missing fields, noise and adversarial cases.',
    metric: 'Exact match · schema validity',
    example: { input: 'Invoice INV-204 from Northwind totals EUR 148.30.', output: '{"invoice_id":"INV-204","vendor":"Northwind","amount":148.3,"currency":"EUR"}' },
    families: ['Flat', 'Nested', 'Arrays', 'Optional', 'Noisy', 'Adversarial'].map(label => ({ label, count: 10 })),
    difficulty: { easy: 2, medium: 14, hard: 28, challenge: 16 },
    tiers: { smoke: 12, core: 60, extended: 60 },
    caution: 'Difficulty labels are authored, not model-calibrated; schema adherence and correct values are different signals.',
  },
  {
    id: 'qa-abstention-controlled-v1', name: 'QA & abstention · v1', group: 'QA & abstention', version: 1,
    status: 'historical', origin: 'repository-authored', capabilityIds: ['qa-abstention'], caseCount: 10,
    purpose: 'Check whether an answer is grounded in the provided context.',
    measures: 'Answering known facts and abstaining when facts are missing.',
    metric: 'QA correctness',
    example: { input: 'Context: Atlas is led by Elena. Question: Who leads Atlas?', output: 'Elena' },
    caution: 'Small baseline without structured difficulty/family labels.',
  },
  {
    id: 'qa-abstention-controlled-v2', name: 'QA & abstention · v2', group: 'QA & abstention', version: 2,
    status: 'current', origin: 'repository-authored', capabilityIds: ['qa-abstention'], caseCount: 60,
    purpose: 'Answer from supplied evidence or abstain when unsupported.',
    measures: 'Fact retrieval, misleading details, missing evidence, near-answers, contradictions and multi-hop reasoning.',
    metric: 'QA correctness · abstention',
    example: { input: 'Context: Atlas is led by Elena. Question: Who leads Atlas?', output: 'Elena' },
    families: ['Direct', 'Distractor', 'Missing', 'Near answer', 'Contradiction', 'Multi-hop'].map(label => ({ label, count: 10 })),
    difficulty: { easy: 10, medium: 18, hard: 25, challenge: 7 },
    tiers: { smoke: 12, core: 60, extended: 60 },
    caution: 'Incorrect guesses and unnecessary abstentions have different failure modes. Difficulty labels remain provisional.',
  },
  {
    id: 'math-reasoning-controlled-v1', name: 'Math reasoning · v1', group: 'Math reasoning', version: 1,
    status: 'historical', origin: 'repository-authored', capabilityIds: ['mathematical-reasoning'], caseCount: 10,
    purpose: 'Sanity-check elementary arithmetic and basic word problems.',
    measures: 'Simple direct calculations, percentages, area and averages.',
    metric: 'Final-answer accuracy',
    example: { input: 'A box has 18 red and 7 blue balls. How many in total?', output: '25' },
    caution: 'Only ten simple cases, with no formal family or difficulty grading; scores may saturate quickly.',
  },
  {
    id: 'math-reasoning-controlled-v2', name: 'Math reasoning · v2', group: 'Math reasoning', version: 2,
    status: 'historical', origin: 'repository-authored', capabilityIds: ['mathematical-reasoning'], caseCount: 40,
    purpose: 'Test basic reasoning across six mathematical families.',
    measures: 'Arithmetic, percentages, multi-step problems, basic algebra, simple logic and constraints.',
    metric: 'Final-answer accuracy',
    example: { input: 'A portfolio drops 20% from 5,000 then gains 25% on the reduced value. Final value?', output: '5000' },
    families: [
      { label: 'Arithmetic', count: 7 }, { label: 'Percentages', count: 7 },
      { label: 'Multi-step', count: 7 }, { label: 'Algebra', count: 7 },
      { label: 'Logic', count: 6 }, { label: 'Constraints', count: 6 },
    ],
    difficulty: { easy: 3, medium: 18, hard: 17, challenge: 2 },
    tiers: { smoke: 12, core: 40, extended: 40 },
    caution: 'Many elementary problems. Different items from v3: an accuracy change across versions is not a model regression.',
  },
  {
    id: 'math-reasoning-controlled-v3', name: 'Math reasoning · v3', group: 'Math reasoning', version: 3,
    status: 'current', origin: 'repository-authored', capabilityIds: ['mathematical-reasoning'], caseCount: 72,
    purpose: 'Probe broader numerical and combinatorial reasoning without long test runs.',
    measures: 'Arithmetic, percentage chains, rates, algebra, permutations and constrained integer problems.',
    metric: 'Final-answer accuracy',
    example: { input: 'Order A, B, C, D, E with A before B before C and D before E. How many valid orders?', output: '10' },
    families: mathFamilies,
    difficulty: { medium: 20, hard: 36, challenge: 16 },
    tiers: { smoke: 12, core: 40, extended: 72 },
    caution: 'Difficulty is authored/provisional, not empirically calibrated. Final answer only; no reasoning trace is scored. The suite caps generation at 256 tokens.',
  },
];

export const activeDatasetGuides = datasetGuides.filter(guide => guide.status === 'current');
export const historicalDatasetGuides = datasetGuides.filter(guide => guide.status === 'historical');

export function getDatasetGuide(datasetId: string): DatasetGuide | undefined {
  return datasetGuides.find(guide => guide.id === datasetId);
}

export function getDatasetVersions(group: string): DatasetGuide[] {
  return datasetGuides
    .filter(guide => guide.group === group && guide.version != null)
    .sort((a, b) => (a.version ?? 0) - (b.version ?? 0));
}

export function difficultyTotal(guide: DatasetGuide): number {
  return Object.values(guide.difficulty ?? {}).reduce((total, n) => total + (n ?? 0), 0);
}
