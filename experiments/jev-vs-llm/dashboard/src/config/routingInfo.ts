/**
 * routingInfo.ts
 *
 * Configuration and documentation content for the Routing (BANKING77) experiment.
 * Centralizes all explanatory texts, examples, and benchmark specifications
 * to keep UI components modular, clean, and easily configurable.
 */

export interface RoutingExample {
  query: string;
  intent: string;
  category: string;
}

export interface RoutingProfileInfo {
  name: string;
  cases: number;
  casesPerClass: string;
  description: string;
  recommended: boolean;
}

export interface RoutingConfig {
  dataset: {
    name: string;
    citation: string;
    license: string;
    totalTestCases: number;
    totalClasses: number;
    sourceSplit: string;
  };
  overview: {
    title: string;
    badge: string;
    conceptSummary: string;
    technicalDefinition: string;
  };
  examples: RoutingExample[];
  whyBanking77: {
    title: string;
    points: Array<{
      headline: string;
      description: string;
    }>;
  };
  routingVsCalibration: {
    routing: {
      title: string;
      type: string;
      analogy: string;
      description: string;
    };
    calibration: {
      title: string;
      type: string;
      analogy: string;
      description: string;
    };
  };
  profiles: RoutingProfileInfo[];
}

export const ROUTING_INFO_CONFIG: RoutingConfig = {
  dataset: {
    name: 'BANKING77',
    citation: 'PolyAI (Casanueva et al., 2020)',
    license: 'CC BY 4.0',
    totalTestCases: 3080,
    totalClasses: 77,
    sourceSplit: 'Official test split (test.csv)',
  },
  overview: {
    title: 'BANKING77 Intent Routing Benchmark',
    badge: 'Closed-Set Classification',
    conceptSummary:
      'In this benchmark, "routing" does not mean network packet forwarding or infrastructure routing. It refers to semantic customer intent routing: classifying inbound banking messages into one of 77 predefined business actions.',
    technicalDefinition:
      'A bounded decision problem over 77 semantically adjacent classes. The system must evaluate the customer inquiry and select the single most accurate intent destination.',
  },
  examples: [
    {
      query: '"I haven\'t received my new card yet, it has been over two weeks."',
      intent: 'card_arrival',
      category: 'Cards',
    },
    {
      query: '"I was charged twice for the same transaction yesterday at the grocery store."',
      intent: 'card_payment_fee_charged',
      category: 'Payments',
    },
    {
      query: '"I completely forgot my PIN code and entered it wrong three times."',
      intent: 'pin_blocked',
      category: 'Security / PIN',
    },
  ],
  whyBanking77: {
    title: 'Why BANKING77 is a Prime Benchmark for JEV vs LLMs',
    points: [
      {
        headline: '77 Semantically Adjacent Classes',
        description:
          'Unlike toy 3-class problems, intents share subtle semantic boundaries (e.g. card_arrival vs card_delivery_estimate vs lost_or_stolen_card), preventing trivial keyword matching.',
      },
      {
        headline: 'Structured Decision vs Token Generation',
        description:
          'JEV evaluates candidate choices via native probability distributions, while LLMs must parse 77 descriptions in-context and generate structured JSON, exposing grammar and reasoning latency.',
      },
      {
        headline: 'Sub-100ms & Cost-Sensitive Production SLA',
        description:
          'Enterprise customer support triage processes millions of tickets. Decision engines and compact on-device models provide massive cost savings over cloud LLMs.',
      },
      {
        headline: 'Zero Synthetic Labels',
        description:
          'The ground truth comes 100% from upstream human annotations in the official PolyAI test set. No LLM hallucinations or synthetic biases exist in evaluation labels.',
      },
    ],
  },
  routingVsCalibration: {
    routing: {
      title: '01 — Routing (Closed-Set)',
      type: 'Closed-Set Intent Classification',
      analogy: 'Which of the 77 doors is the right door?',
      description:
        'The query is guaranteed to belong to one of the 77 supported banking categories. The model must pick exactly one best destination.',
    },
    calibration: {
      title: '02 — Calibration (Open-Set)',
      type: 'Open-Set & OOS Detection',
      analogy: 'Do you realize when NONE of the 77 doors is right?',
      description:
        'Mixes in-scope banking queries with out-of-scope requests (CLINC150) mapped to "other". Tests rejection capability and confidence score reliability.',
    },
  },
  profiles: [
    {
      name: 'budget',
      cases: 77,
      casesPerClass: '1 per class',
      description: 'Ultra-fast, cost-efficient sanity check covering every single intent.',
      recommended: true,
    },
    {
      name: 'quick',
      cases: 154,
      casesPerClass: '2 per class',
      description: 'Rapid regression and integration validation run.',
      recommended: false,
    },
    {
      name: 'standard',
      cases: 770,
      casesPerClass: '10 per class',
      description: 'Default statistically balanced comparative experiment.',
      recommended: false,
    },
    {
      name: 'full',
      cases: 3080,
      casesPerClass: '~40 per class',
      description: 'Complete official test set for maximum scientific confidence.',
      recommended: false,
    },
  ],
};
