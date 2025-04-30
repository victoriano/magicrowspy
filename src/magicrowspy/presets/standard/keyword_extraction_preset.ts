import { AIEnrichmentBlockConfig } from '../schemas/AIEnrichmentBlockSchema';

/**
 * Keyword Extraction Preset
 * 
 * This preset extracts key topics and entities from text.
 * It identifies important keywords and the main topic of the text.
 */
export const keywordExtractionConfig: AIEnrichmentBlockConfig = {
  integrationName: 'openai',
  model: 'gpt-3.5-turbo',
  mode: 'preview',
  previewRowCount: 2,
  outputFormat: 'newColumns',
  outputs: [
    {
      name: 'Keywords',
      prompt: 'Extract the most important keywords from this text. Respond with up to 5 keywords separated by commas: {{description}}',
      outputType: 'categories'
    },
    {
      name: 'Main Topic',
      prompt: 'What is the main topic of this text? Respond with a single word or short phrase: {{description}}',
      outputType: 'text'
    }
  ]
};

/**
 * Metadata for the Keyword Extraction preset
 */
export const keywordExtractionPreset = {
  id: 'keyword-extraction',
  name: 'Keyword Extraction',
  description: 'Extract key topics and entities from text',
  config: keywordExtractionConfig
};
