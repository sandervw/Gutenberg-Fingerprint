# Site

## Home

**UC-01 Read the corpus summary.** The Reader opens `/`. They see the title "Gutenberg Fiction Metrics", a line saying measures are z-scores, the number of works in the corpus, and the date the latest work arrived.

**UC-02 Browse the Weirdest Works.** On `/`, the Reader sees a "Weirdest Works" table with Work, Author, Genre, Words, and Excess columns, highest Excess first, 25 rows per page. Clicking a row opens that work's page.

**UC-03 Compare vocabulary.** On `/`, the Reader sees a "Vocabulary Overlap" bar chart with one bar per author.

## Works

**UC-04 List works.** The Reader opens `/works`. They see a table with Title, Author, Words, Genre, and Flags columns.

**UC-05 Filter works.** On `/works`, the Reader picks an author, picks a genre, or types part of a title. The table shows only matching works. Choosing "All authors" and "All genres" and clearing the title shows every work again.

**UC-06 Filter by flags.** On `/works`, the Reader picks juvenile, play, poetry, or translation values. The table narrows to works with those flags.

**UC-07 Read a work.** The Reader clicks a work. Its page shows the title, the author as a link, the genre, prose type, and word count, then "Departure from the Author's Norm", "Work Signature", and "Sentence Type Mix" charts. The author link opens the author's page.

## Authors

**UC-08 List authors.** The Reader opens `/authors`. They see a searchable table with Author, Works, and Words columns.

**UC-09 Search authors.** On `/authors`, the Reader types part of a name in the search box. The table shows only matching authors.

**UC-10 Read an author.** The Reader clicks an author. Their page shows the name, works in corpus, total words, a "Signature Stylometrics" chart, a Definitions section that opens to list each metric, and a "Sentence Breakdown" chart.

## Navigation and appearance

**UC-11 Navigate.** From any page, the Reader reaches Home, Works, and Authors through the site navigation.

**UC-12 Missing page.** The Reader opens an address that does not exist. They see "Page Not Found" and a link back to the home page.

**UC-13 Phone and themes.** At phone width every page reads without sideways scrolling. The Reader can switch between light and dark themes, and text stays readable in both.
