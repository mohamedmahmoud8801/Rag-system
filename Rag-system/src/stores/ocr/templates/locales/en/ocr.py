from string import Template


#### OCR PROMPTS ####

#### Extract Text ####

extract_text_prompt = Template("\n".join([
    "Extract all visible text from the provided image.",
    "Preserve the original reading order as much as possible.",
    "Return only the extracted text.",
    "Do not add explanations or information that is not present in the image.",
]))


#### Document ####

document_prompt = Template("\n".join([
    "Extract and organize all visible text from this document.",
    "Preserve:",
    "- headings",
    "- paragraphs",
    "- lists",
    "- tables",
    "- important information",
    "Return the content in a structured and readable format.",
]))


#### Table ####

table_prompt = Template("\n".join([
    "Extract the table content from the provided image.",
    "Preserve:",
    "- column names",
    "- row values",
    "- table structure",
    "Return the table content in a structured format.",
]))