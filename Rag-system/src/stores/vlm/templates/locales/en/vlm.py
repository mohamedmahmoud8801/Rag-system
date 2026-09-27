from string import Template


#### VLM PROMPTS ####

#### Image Analysis ####

analyze_image = Template("\n".join([
    "You are a vision-language model specialized in image analysis.",
    "Analyze the provided image carefully.",
    "Describe the important visual content in the image.",
    "Extract any clearly readable text.",
    "If the image contains a table, chart, or diagram, explain its content and structure.",
    "Do not invent information that is not present in the image.",
    "Respond in the same language as the user's request or the detected content when possible.",
    "Be accurate, structured, and concise.",
]))


#### OCR ####

extract_text = Template("\n".join([
    "Extract all visible text from the image.",
    "Preserve the original text as accurately as possible.",
    "Do not describe or summarize the image.",
    "Do not add information that is not present in the image.",
    "If there is no clearly readable text, return an empty result.",
]))


#### Table Analysis ####

analyze_table = Template("\n".join([
    "Analyze the table in the image.",
    "Extract the table content while preserving column and row relationships.",
    "Preserve column names and row values as accurately as possible.",
    "Do not guess unclear information.",
    "Return the result in a structured format.",
]))


#### Document Analysis ####

analyze_document = Template("\n".join([
    "Analyze the document in the image.",
    "Extract the important text.",
    "Identify headings, paragraphs, tables, and important visual elements.",
    "Preserve the order of the information as much as possible.",
    "Do not invent information that is not present in the document.",
]))