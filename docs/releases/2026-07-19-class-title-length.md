# Class and exam-prep title length

Class and exam-prep titles now have a product-level limit of 120 characters in both creation and edit
flows. The shared creation form displays a live counter and prevents additional input, while all four
backend create/update serializers reject direct API requests beyond the same limit with a Persian
validation message.

The shared intake copy now follows the selected pipeline: exam-prep mode displays «اطلاعات آمادگی
آزمون» and «عنوان آمادگی آزمون» instead of the class labels.

No schema migration or environment change is required. The database column remains 255 characters to
preserve compatibility with historical rows; the tighter limit applies to new or edited titles.
