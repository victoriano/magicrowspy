import { AIEnrichmentBlockConfig } from '../schemas/AIEnrichmentBlockSchema';

/**
 * Sentiment Analysis Preset
 * 
 * This preset analyzes text sentiment and categorizes it as positive, negative, or neutral.
 * It also provides a numeric sentiment score on a scale from 1 to 10.
 */
export const sentimentAnalysisConfig: AIEnrichmentBlockConfig = {
  integrationName: 'openai',
  model: 'gpt-3.5-turbo',
  mode: 'preview',
  previewRowCount: 2,
  outputFormat: 'newColumns',
  outputs: [
    {
      name: 'Sentiment',
      prompt: 'Analyze the sentiment of the following text and respond with exactly one of: "positive", "negative", or "neutral". Text: {{description}}',
      outputType: 'singleCategory',
      outputCategories: [
        { name: 'positive', description: 'Text has overall positive sentiment' },
        { name: 'negative', description: 'Text has overall negative sentiment' },
        { name: 'neutral', description: 'Text has neutral or mixed sentiment' }
      ]
    },
    {
      name: 'Sentiment Score',
      prompt: 'On a scale from 1 to 10, where 1 is extremely negative and 10 is extremely positive, rate the sentiment of the following text. Respond with just the number. Text: {{description}}',
      outputType: 'number'
    }
  ]
};

/**
 * Metadata for the Sentiment Analysis preset
 */
export const sentimentAnalysisPreset = {
  id: 'sentiment-analysis',
  name: 'Sentiment Analysis',
  description: 'Analyze text sentiment and categorize as positive, negative, or neutral',
  config: sentimentAnalysisConfig
};
