import { AIEnrichmentBlockConfig } from '../schemas/AIEnrichmentBlockSchema';

export const ISCOPerplexityTasksConfig: AIEnrichmentBlockConfig = {
  "integrationName": "myPerplexity",
  "model": "sonar",
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
        { "name": "Germany", "description": "Businesses based in Germany" },
        { "name": "France", "description": "Businesses based in France" },
        { "name": "United Kingdom", "description": "Businesses based in the United Kingdom" },
        { "name": "Italy", "description": "Businesses based in Italy" },
        { "name": "Spain", "description": "Businesses based in Spain" }
      ]
    }
  ]
};

export const ISCOPerplexityTasksPreset = {
  id: 'isco-tasks-perplexity',
  name: 'ISCO Tasks (Perplexity)',
  description: 'Identify tasks with high automation potential using Perplexity',
  config: ISCOPerplexityTasksConfig
}; 