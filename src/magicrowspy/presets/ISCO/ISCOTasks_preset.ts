// src/shared/examples/llmProcessingExamples.ts
import { AIEnrichmentBlockConfig } from '../schemas/AIEnrichmentBlockSchema';

/**
 * Example of an LLM processing job that identifies automation tasks for professions
 * and rates their novelty based on NACE and ISCO codes
 */
export const ISCOtasksConfig: AIEnrichmentBlockConfig = {
  "integrationName": "myOpenAI",
  "model": "gpt-4.1-nano",
  "temperature": 0.2,
  "mode": "preview",
  "previewRowCount": 2,
  "outputFormat": "newRows",
  "contextColumns": ["nace", "isco"],
  "outputs": [
    {
      "name": "automation_tasks",
      "prompt": "For the profession described by NACE code {{nace}} and ISCO code {{isco}}, identify 5 specific tasks with high AI automation potential.",
      "outputType": "text",
      "outputCardinality": "multiple"
    },
    {
      "name": "best_countries_match",
      "prompt": "Based on the industry sector with NACE code {{nace}} and occupation with ISCO code {{isco}}, analyze which of the following European countries have the strongest and most advanced industry in this specific sector and occupation. Consider factors like technological advancement, market leadership, innovation, workforce expertise, and industry presence. Select 1-3 most appropriate countries and provide reasoning based on specific company names that are strong in those countries in this industry",
      "outputType": "category",
      "outputCardinality": "multiple",
      "outputCategories": [
        {
          "name": "Germany",
          "description": "Businesses based in Germany"
        },
        {
          "name": "France",
          "description": "Businesses based in France"
        },
        {
          "name": "United Kingdom",
          "description": "Businesses based in the United Kingdom"
        },
        {
          "name": "Italy",
          "description": "Businesses based in Italy"
        },
        {
          "name": "Spain",
          "description": "Businesses based in Spain"
        }
      ]
    }
  ]
};

/**
 * Metadata for the Data Enrichment preset
 */
export const ISCOTasksPreset = {
  id: 'isco-tasks',
  name: 'ISCO Tasks',
  description: 'Identify tasks with high automation potential based on NACE and ISCO codes',
  config: ISCOtasksConfig
};
