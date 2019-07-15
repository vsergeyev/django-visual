// Visual Django IDE - Utils to work with SQLITE3 files

function load_db(path, el) {
	var content = [];

	var xhr = new XMLHttpRequest();

	xhr.open('GET', '/ide/open_file/?path=' + path, true);
	xhr.responseType = 'arraybuffer';

	xhr.onload = function(e) {
		var data = new Uint8Array(this.response);
		var db = new SQL.Database(new Uint8Array(data));
		var tables = db.prepare("SELECT * FROM sqlite_master WHERE type='table' ORDER BY name");

		while (tables.step()) {
            var rowObj = tables.getAsObject();
            var name = rowObj.name;

            var sel = db.exec("SELECT * FROM '" + name + "'");

            content.push([name, sel]);
        }

		console.log(content);
		render_db(content, el);
	};

	xhr.onerror = function(e) {
		console.log("** An error occurred during file open");
		$("#" + el).text("** An error occurred during file open");
	};

	xhr.send();
}

function render_db(data, el) {
	$('<div class="row small p-3"><div class="nav flex-column nav-pills col col-md-3" id="' + el + '-tables" role="tablist" aria-orientation="vertical"></div>'
	  + '<div class="tab-content col col-md-9" id="' + el + '-data"></div></div>').appendTo("#" + el);

	data.forEach(function (item, index) {
		var name = item[0]; //table name
		var select_wrapper = item[1];
		var select;  // 0 element in select_wrapper, select * from table
		var count = 0;

		// console.log(item);

		if (select_wrapper.length) {
			select = select_wrapper[0];
			count = select.values.length;
		}

		$('<a class="nav-link bg-blue" data-toggle="pill" id="' + el + '-tables' + index + '" '
	      + 'href="#' + el + '-data' + index + '" role="tab" aria-controls="' + el + '-data' + index + '" '
	      + 'aria-selected="false">' + name + ' (' + count + ' )</a>').appendTo("#" + el + '-tables');

		var data_table = "<div class='table-responsive'><table class='table table-striped table-sm table-ellipsis'><thead class='thead-dark'><tr>";

		if (count > 0) {
			select.columns.forEach(function (val) {
				data_table += "<th>" + val + "</th>";
			});
			data_table += "</tr></thead><tbody>";

			select.values.forEach(function (val) {
				data_table += "<tr>";

				val.forEach(function (x) {
					data_table += "<td>" + x + "</td>";
				});

				data_table += "</tr>";
			});
			data_table += "</tbody></table></div>";

		} else {
			data_table += "<th>No items in selected table</th></tr></thead></table>";
		}

		$('<div class="tab-pane fade" id="' + el + '-data' + index + '" '
		  + 'role="tabpanel" aria-labelledby="">'
		  + data_table + '</div>').appendTo("#" + el + '-data');
	});

	$('#' + el + '-tables0').tab('show');
}
