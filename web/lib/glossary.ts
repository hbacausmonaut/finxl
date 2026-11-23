/** Plain-language notes for the lines readers ask about most, matched on the label as printed. */
const NOTES: Array<[RegExp, string]> = [
  [/^revenue from operations/i, "Sales of goods and services from the company's main business, before any other income."],
  [/^other income/i, "Income outside the main business: interest, dividends, gains on investments."],
  [/changes? in inventor/i, "Adjusts cost for stock built up or drawn down in the year. A negative figure means stock rose."],
  [/^finance costs?/i, "Interest and other costs of borrowing."],
  [/^depreciation/i, "The year's share of the cost of long-lived assets, charged as they wear out. No cash leaves."],
  [/^deferred tax(?! (assets|liabilit))/i, "Tax that relates to this year's profit but is paid or recovered in later years."],
  [/^profit (\(loss\) )?before tax/i, "Total income less total expenses, before income tax."],
  [/^(net )?profit (\(loss\) )?for the (year|period)|^profit after tax/i, "What is left for shareholders after tax. Also called net profit."],
  [/^basic|^diluted|earnings per (equity )?share/i, "Profit for the year divided by the weighted number of shares outstanding."],
  [/capital work[- ]in[- ]progress/i, "Money spent on plant or buildings that are not yet ready for use."],
  [/intangible assets/i, "Assets without physical form: software, licences, brands, goodwill."],
  [/^other equity/i, "Retained profits and other reserves that belong to shareholders."],
  [/deferred tax liabilit/i, "Tax the company expects to pay later because books and tax rules time things differently."],
  [/^trade payables/i, "Amounts owed to suppliers for goods and services already received."],
  [/^trade receivables/i, "Amounts customers owe for sales already made."],
  [/^net cash.*operat/i, "Cash the business itself produced, after working capital and tax."],
  [/^net cash.*investing/i, "Cash spent on, or received from, long-term assets and investments."],
  [/^net cash.*financing/i, "Cash raised from or returned to lenders and shareholders."],
  [/^(purchase|acquisition) of property, plant/i, "Cash paid for plant, equipment and other long-lived assets. Often called capex."],
  [/^other comprehensive income/i, "Gains and losses that skip the profit line, such as revaluations and currency translation."],
]

export const glossaryFor = (label: string) => NOTES.find(([rx]) => rx.test(label.trim()))?.[1]
