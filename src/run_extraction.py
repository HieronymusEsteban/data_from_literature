#!/usr/bin/env python
# coding: utf-8

# # Scale extraction
# Reads Table 1 **directly from the PDF** (pdfplumber, no hardcoded values).
# Produces TWO outputs from one run:
# 1. **Verification view** -> `raw_extracted/<pdf_name>/` (raw packed layout + parsed layout, for eyeballing)
# 2. **Long-format CSV** -> `consolidated/<pdf_name>/`
# 
# Run top to bottom.

# In[1]:

# In[2]:

ROOT = Path(__file__).resolve().parents[1]



from scaffold import run_extraction
from extract_modestin_2004 import extract

# In[3]:


import re
from pathlib import Path
import pandas as pd
import pdfplumber

#SCHEMA_COLUMNS = ["publication","scale","data_type","sample","subsample","sample_size","value"]
#ALLOWED_DATA_TYPES = {"mean","median","sd","minimum","maximum","individual"}
#ALLOWED_SAMPLES = {"patients","healthy_controls"}
#NA_MARKER = "NA"

# ## Run it
# Set the three paths; everything else is automatic.
# `raw_df` and `parsed_df` display below for visual verification against the PDF.

# In[4]:


ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
PDF_PATH         = ROOT / "data" / "raw_pdfs" / "DES-T_Modestin_et_al_2004.pdf"
RAW_EXTRACTED_DIR = ROOT / "data" / "raw_extracted"
CONSOLIDATED_DIR  = ROOT / "data" / "consolidated"

raw_df, parsed_df, long_df, hardcoded = run_extraction(
    PDF_PATH, extract, RAW_EXTRACTED_DIR, CONSOLIDATED_DIR)
print("\nhardcoded:", hardcoded)

# ### Verification — raw layout (compare against the PDF table)

# In[5]:


raw_df

# ### Verification — parsed layout (mean/sd/median split out)

# In[6]:


parsed_df

# ### Long-format (what goes to consolidated/)

# In[7]:


long_df
