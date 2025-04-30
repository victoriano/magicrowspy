import { AIEnrichmentBlockConfig } from '../schemas/AIEnrichmentBlockSchema';

/**
 * Data Enrichment Preset
 * 
 * This preset generates additional insights and details from existing data.
 * It creates startup ideas and examples for specific sectors and occupations.
 */
export const dataEnrichmentConfig: AIEnrichmentBlockConfig = {
  integrationName: 'perplexity',
  model: 'sonar',
  mode: 'preview',
  previewRowCount: 2,
  outputFormat: 'newRows',
  contextColumns: ['nace', 'isco'],
  outputs: [
    {
      name: 'Startup Ideas',
      prompt: 'For this sector and occupation: {{nace}} {{isco}} disrupting using new genAI capabilities',
      outputType: 'text'
    },
    {
      name: 'Example of Startups',
      prompt: 'For this sector and occupation: {{nace}} {{isco}} list disrupting startups using AI already to serve problems',
      outputType: 'text'
    }
  ]
};

/**
 * Metadata for the Data Enrichment preset
 */
export const dataEnrichmentPreset = {
  id: 'data-enrichment',
  name: 'Data Enrichment',
  description: 'Generate additional insights and details from existing data',
  config: dataEnrichmentConfig
};
