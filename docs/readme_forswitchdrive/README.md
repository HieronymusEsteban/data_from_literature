# all_consolidated.csv

## Purpose

`all_consolidated.csv` contains data from the scientific literature 
that was obtained by applying the psychometric scales 
(structured interviews and questionnaires) that are also used 
in the project **HearingThreat**.

These data can be used for comparison against the results obtained in 
HearingThreat.

## Table Structure

`all_consolidated.csv` is designed in **long form** in order to accommodate 
data from different data schemas and to support data management. This file will grow as more data will be added.

`pub_info_table.csv` contains sample information on the publication level 
and is also designed to support data management as well as documentation. This file will grow as more data will be added.

`output_excel` contains user friendly data extracts from `all_consolidated.csv` 
for visual inspection. `output_excel` is generated automatically and can be updated if need be.

## Limitations:
### mean values:
So far `output_excel` only contains **data on the subscale or total score level** and only shows **mean values**. 
User friendly tables with item-level data will follow. 
Therefore, for publications that report median values rather than mean values, 
or publications that only have item level data blank spaces may show up on `output_excel`.

### No time dimension in data schema:
The current data schema does not model a time dimension for longitudinal studies.
Therefore baseline and follow-up measurements are modelled as subsamples (which is
strictly speaking wrong). So far, however, longitudinal data is rare in this database.

### Incomplete information about sample structure:
The data was extracted from publications (pdf documents) without access to the raw data. 
Therefore, the exact sample structure is often obscure, i.e. sample size may differ between
measurements of different subscales, without clear indication if and to what degree these
subsamples overlap. Therefore, in some cases sample sizes can only be calculated for each 
subscale measurement individually. 

## Code:
ETL-code as well as the code used to generate the output_excel.xlsx file can be found on: 
https://github.com/HieronymusEsteban/data_from_literature

## Data:
The folder data mirrors in structure and in content the data folder that was used in the project on github (see above).



