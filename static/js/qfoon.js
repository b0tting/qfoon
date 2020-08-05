/**
 * Created by Mark on 22-2-2017.
 */
    var table = ""

    function get_request_param(name){
        matches = new RegExp('[?&]'+encodeURIComponent(name)+'=([^&]*)').exec(location.search)
        return matches ? decodeURIComponent(matches[1]) : false
    }

    function get_my_time() {
          date = new Date();
          return date.getHours() + ":" + ( (date.getMinutes()<10?'0':'') + date.getMinutes() )
      }

    function get_my_date() {
        date = new Date()
        months = new Array('Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni', 'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'),
        curMonth = months[date.getMonth()]
        var onejan = new Date(date.getFullYear(),0,1);
        weeknum = Math.ceil((((date - onejan) / 86400000) + onejan.getDay()+1)/7);
        return date.getDate() + " " + curMonth + ", week " + weeknum
      }


    function jira_image_url_to_qfoon(url, jiraurl){
        //console.log("URL: " + url + "  - JIRAURL: " + jiraurl + " - RESULT: " + url.replace(jiraurl, ""))
        return '/jira_image' + url.replace(jiraurl, "")
    }

     function refresh_jira() {
          table.ajax.reload();
          $("#jiradate").text(get_my_time());
     }


    function refresh_phones() {
        $.getJSON( "phones", function( data ) {
            try {
                for (target in data) {
                    id_target = "#" + target.replace(" ", "_");
                    if (data[target] && $(id_target).length) {
                        if (data[target][0]) {
                            $(id_target).html(data[target][0].replace("(", "<br>("));
                            $(id_target + "_label").removeClass("bg-red");
                            $(id_target + "_label").addClass("bg-green")
                        } else {
                            $(id_target).html("Geen doorschakeling");
                            $(id_target + "_label").addClass("bg-red");
                            $(id_target + "_label").removeClass("bg-green")
                        }
                    }
                }
            } catch(err) {
                console.log("Got an error trying to get phone info" + err)
            }
            $("#phonedate").text(get_my_time())
        }).fail(function() {console.log("Got tough love from the server trying to get phone info")})
    }

    function startTime(id) {
        var today = new Date();
        var h = today.getHours();
        var m = today.getMinutes();
        if (m < 10) {
            m = "0" + m
        }
        $('#'+id+'').text(h + ":" + m)
        setTimeout(startTime, 500, id);
    }





