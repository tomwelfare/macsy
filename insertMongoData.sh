mongo testdb --eval 'db.ARTICLE_2010.insert({_id: ObjectId("4c3658700000000000000000"), T: "Title 1", D: "Description 1", C: "Content 1", Tg: [1], FOR : [4]});'
mongo testdb --eval 'db.ARTICLE_2011.insert({_id: ObjectId("4deffef00000000000000000"), T: "Title 2", D: "Description 2", C: "Content 2", Tg: [1, 2], FOR : [5]});'
mongo testdb --eval 'db.ARTICLE_2012.insert({_id: ObjectId("4fd526f00000000000000000"), T: "Title 3", D: "Description 3", C: "Content 3", Tg: [1, 2, 3], FOR : [4, 5]});'
mongo testdb --eval 'db.ARTICLE_TAGS.insert([{_id: 1, Nm: "Tag_1", Ctrl: 0},{_id: 2, Nm: "Tag_2", Ctrl: 0},{_id: 3, Nm: "Tag_3", Ctrl: 0},{_id: 4, Nm: "FOR>Tag_4", Ctrl: 1},{_id: 5, Nm: "POST>Tag_5", Ctrl: 1}]);'
